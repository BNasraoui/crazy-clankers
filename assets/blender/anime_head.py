"""Shared UV-preserving head mesh, neck, ears, scalp and supplied hair paths.

shape is a head_shape.HeadShape; locks are (control_points, width, depth) in
metres relative to the eye centre. Materials use face/skin/hair/ear_ink roles.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

def build_head_mesh(A,C,mats,materials,root,centre,neck,tilt_spec, shape, locks):
    sections = shape.sections
    interp = shape.section
    surface = lambda theta, y: Vector(shape.surface(theta, y))
    uv_bottom = -.115*shape.height
    uv_height = .240*shape.height
    b=C.Builder(mats)
    uv=b.bm.loops.layers.uv.new('UVMap')
    def face(vs,mat,coords=None):
        f=b.bm.faces.new(vs);f.material_index=mats.index(mat)
        if coords:
            for l,q in zip(f.loops,coords): l[uv].uv=q
        return f
    # Dense rings at the nose/lip transitions; face is one continuous surface.
    ys=sorted(set([p[0] for p in sections]+[(-.108+i*.225/48)*shape.height for i in range(49)]))
    n=64; rings=[]
    for y in ys:
        rings.append([b.bm.verts.new(A.gv(centre+surface(-math.pi+2*math.pi*i/n,y))) for i in range(n)])
    for j in range(len(ys)-1):
        v0=(ys[j]-uv_bottom)/uv_height;v1=(ys[j+1]-uv_bottom)/uv_height
        for i in range(n):
            k=(i+1)%n
            face([rings[j][i],rings[j][k],rings[j+1][k],rings[j+1][i]],'face',[(i/n,v0),((i+1)/n,v0),((i+1)/n,v1),(i/n,v1)])
    face(list(reversed(rings[0])),'skin');face(rings[-1],'skin')
    # Actual neck, ears with inset concha and helix, never texture ears on a plane.
    A.limb(b,'skin',[neck+Vector((0,-.015,-.010)),neck+Vector((0,.050,-.003)),centre+Vector((0,-.067,-.012))],
           [(.044,.042),(.040,.041),(.043,.041)],sides=20,steps=2)
    for sx in [-1,1]:
        ec=centre+Vector((sx*interp(0)[0],-.020,-.002))
        A.blob(b,'skin',ec,(.013,.024,.016),u=16,v=10)
        # Small helix line embedded on the outer/front face.
        pts=[ec+Vector((sx*x,y,z)) for x,y,z in [(.005,-.013,.012),(.009,.001,.016),(.006,.014,.012),(-.001,.014,.014),(-.005,.003,.016)]]
        A.limb(b,'ear_ink',pts,[(.001,.001)]*len(pts),sides=5,steps=2)
    # Scalp with wavy hairline; stays underneath flowing clumps.
    cap=[];N=48;R=12
    for j in range(R+1):
        row=[]
        for i in range(N):
            a=-math.pi+2*math.pi*i/N
            front=max(0,math.cos(a)); back=max(0,-math.cos(a))
            low=.010+.058*front-.049*back+.004*math.sin(5*a)
            phi=(low+(.119-low)*j/R)*shape.height
            rx,zf,zb=interp(min(phi,.117*shape.height))
            shrink=max(0,(.119*shape.height-phi)/(.002*shape.height)) if phi>.117*shape.height else 1
            x=(rx+.009)*math.sin(a)*shrink
            z=((zf+.012)*max(math.cos(a),0)**1.0 if math.cos(a)>0 else (zb+.012)*math.cos(a))*shrink
            p=centre+Vector((x,phi,z))
            row.append(b.bm.verts.new(A.gv(p)))
        cap.append(row)
    for j in range(R):
        for i in range(N):
            k=(i+1)%N
            face([cap[j][i],cap[j][k],cap[j+1][k],cap[j+1][i]],'hair',[(.5,.5)]*4)
    face(cap[-1],'hair',[(.5,.5)]*N)
    # broad sweep clumps. Coordinates local to eye-centre. Roots submerged;
    # rounded convex transverse profiles, flowing S-curves and short turned ends.
    for controls,width,depth in locks:
        pts=A.catmull([centre+Vector(p) for p in controls],4)
        rows=[];ns=8
        previous=None
        for j,p in enumerate(pts):
            t=j/(len(pts)-1)
            tangent=(pts[min(j+1,len(pts)-1)]-pts[max(j-1,0)]).normalized()
            normal=(p-centre-Vector((0,.025,-.012))).normalized()
            across=tangent.cross(normal).normalized()
            if previous is not None and across.dot(previous)<0: across=-across
            if across.length<.1 and previous is not None: across=(previous-tangent*previous.dot(tangent)).normalized()
            previous=across.copy()
            normal=across.cross(tangent).normalized()
            # broad for first 75%, then a curved fine end, no spear beyond the path
            w=width*(.60+.40*math.sin(math.pi*min(t*1.4,1)))*(1-t**4)+.0005
            thick=depth*.60*(.45+.55*math.sin(math.pi*t))
            row=[]
            for k in range(ns):
                a=2*math.pi*k/ns
                pos=p+across*(math.cos(a)*w)+normal*(math.sin(a)*thick)
                row.append(b.bm.verts.new(A.gv(pos)))
            rows.append(row)
        for j in range(len(rows)-1):
            for k in range(ns):
                l=(k+1)%ns
                face([rows[j][k],rows[j][l],rows[j+1][l],rows[j+1][k]],'hair',[(k/ns,1-j/(len(rows)-1)),((k+1)/ns,1-j/(len(rows)-1)),((k+1)/ns,1-(j+1)/(len(rows)-1)),(k/ns,1-(j+1)/(len(rows)-1))])
        face(list(reversed(rows[0])),'hair',[(.5,.99)]*ns);face(rows[-1],'hair',[(.5,.01)]*ns)
    # Collapse coincident pole vertices without destroying per-loop UV seams.
    bmesh.ops.remove_doubles(b.bm,verts=list(b.bm.verts),dist=1e-7)
    # Finish directly, preserving loop UVs (Builder's canonical reconstruction drops them).
    bmesh.ops.recalc_face_normals(b.bm,faces=list(b.bm.faces))
    tilt=Matrix.Identity(3)
    for degrees,axis in tilt_spec: tilt=A.grot(degrees,axis)@tilt
    bmesh.ops.rotate(b.bm,verts=list(b.bm.verts),cent=A.gv(neck),matrix=tilt)
    bmesh.ops.translate(b.bm,verts=list(b.bm.verts),vec=-A.gv(neck))
    # Match the cab helper's deterministic ordering, but retain each UV loop.
    C.canonical_order(b.bm)
    vertices=[tuple(v.co) for v in b.bm.verts]
    polygons=[];uv_polygons=[];material_indices=[]
    for f in b.bm.faces:
        loops=list(f.loops)
        start=min(range(len(loops)),key=lambda i:loops[i].vert.index)
        loops=loops[start:]+loops[:start]
        polygons.append([l.vert.index for l in loops])
        uv_polygons.append([tuple(l[uv].uv) for l in loops])
        material_indices.append(f.material_index)
    b.bm.free()
    mesh=bpy.data.meshes.new('head')
    mesh.from_pydata(vertices,[],polygons)
    layer=mesh.uv_layers.new(name='UVMap')
    for polygon,coords,material_index in zip(mesh.polygons,uv_polygons,material_indices):
        polygon.material_index=material_index
        for li,coord in zip(polygon.loop_indices,coords): layer.data[li].uv=coord
    for name in mats: mesh.materials.append(materials[name])
    mesh.shade_smooth()
    obj=bpy.data.objects.new('head',mesh);bpy.context.scene.collection.objects.link(obj)
    obj.parent=root;obj.location=A.gv(neck)
    # Face-only normals combine the real profile with a broad anime cheek normal.
    inv=tilt.inverted();normals=[]
    faceverts={v for p in mesh.polygons if mats[p.material_index]=='face' for v in p.vertices}
    for v in mesh.vertices:
        n=v.normal.copy()
        if v.index in faceverts:
            q=A.to_game(inv@(v.co+A.gv(neck)-A.gv(neck))+A.gv(neck))-centre
            if q.z>0 and q.y<.066:
                stylized=Vector((q.x*3.0,(q.y+.005)*2.2,.95)).normalized()
                blend=.35 if abs(q.x)>.018 else .25
                n=n.lerp(tilt@A.gv(stylized),blend).normalized()
        normals.append(n)
    mesh.normals_split_custom_set_from_vertices(normals)
    return obj
