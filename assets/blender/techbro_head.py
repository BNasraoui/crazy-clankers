"""Tech Bro head: section-modelled facial volume, cylindrical UVs, broad swept hair.

All modelling dimensions are metres in game coordinates. No lighting in textures.
The back seam of the head unwrap is at +/- pi; hair islands run root to tip.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

# y from eye level, half width, face depth, rear depth. Chin is a short plane,
# jaw has a deliberate mandibular corner, cheek reaches widest below the temples.
SECTIONS = [
    (-.108,.029,.074,.002),(-.102,.039,.080,.012),(-.086,.059,.081,.025),
    (-.060,.074,.078,.042),(-.038,.077,.080,.067),(-.019,.082,.078,.085),
    (0,.081,.077,.096),(.021,.080,.081,.101),(.042,.080,.083,.103),
    (.064,.079,.078,.099),(.085,.071,.066,.089),(.103,.052,.045,.066),
    (.115,.019,.016,.027),(.117,.002,.002,.003)]


def interp(y):
    i = next((i for i in range(1,len(SECTIONS)) if SECTIONS[i][0]>=y), len(SECTIONS)-1)
    a,b=SECTIONS[i-1],SECTIONS[i]
    t=max(0,min(1,(y-a[0])/(b[0]-a[0])))
    return tuple(a[k]+(b[k]-a[k])*t for k in range(1,4))


def surface(theta,y):
    rx,zf,zb=interp(y)
    s,c=math.sin(theta),math.cos(theta)
    x=rx*s
    # Slightly flatter facial arc across the eyes than the back of the skull.
    z=(zf * max(c,0)**.55 if c>=0 else zb*c)
    if c>0:
        # Integrated bridge, nose tip, nostril wings, muzzle and lower lip/chin.
        z += .018*math.exp(-(x/.010)**2-((y+.022)/.030)**2)
        z += .016*math.exp(-(x/.012)**2-((y+.037)/.010)**2)
        z += .004*math.exp(-(x/.023)**2-((y+.043)/.006)**2)
        z += .007*math.exp(-(x/.038)**4-((y+.063)/.019)**2)
        z -= .002*math.exp(-((abs(x)-.034)/.025)**2-(y/.014)**2)
    return Vector((x,y,z))


def paint_head(A,palette):
    """Rasterize the committed transparent facial ink onto the cylindrical UV atlas.

    This is inverse UV sampling, not camera projection: both eyes and the smile
    travel around the cheek surface with its seam at the back of the head.
    Only pigment/ink/eye whites are in the source, never skin or lighting.
    """
    import numpy as np
    from pathlib import Path
    decal=A.Image.open(Path(__file__).parent/'textures/techbro-face-decal.png').convert('RGBA')
    source=np.asarray(decal,dtype=np.float32)/255
    # Remove neutral tonal variation in the generated whites; keep alpha and ink.
    rgb=source[:,:,:3]
    white=(rgb.min(axis=2)>.58)&((rgb.max(axis=2)-rgb.min(axis=2))<.10)
    rgb[white]=np.array((255,252,243))/255
    # Brows are flat brown pigment; no gradient from the generated drawing.
    rgb[:505]=np.array(A.rgb(0x352A24))/255
    size=2048
    u=(np.arange(size)+.5)/size
    v=1-(np.arange(size)+.5)/size
    y=v*.240-.115
    rx=np.interp(y,[p[0] for p in SECTIONS],[p[1] for p in SECTIONS])
    theta=(u-.5)*2*math.pi
    x=rx[:,None]*np.sin(theta)[None,:]
    sx=x/.000145+650
    sy=np.broadcast_to((570-y/.000160)[:,None],sx.shape)
    inside=(sx>=0)&(sx<decal.width-1)&(sy>=0)&(sy<decal.height-1)&(np.cos(theta)[None,:]>0)
    sx=np.clip(sx,0,decal.width-2);sy=np.clip(sy,0,decal.height-2)
    ix=sx.astype(int);iy=sy.astype(int);fx=(sx-ix)[...,None];fy=(sy-iy)[...,None]
    sample=(source[iy,ix]*(1-fx)+source[iy,ix+1]*fx)*(1-fy)+(source[iy+1,ix]*(1-fx)+source[iy+1,ix+1]*fx)*fy
    alpha=sample[:,:,3:4]*inside[:,:,None]
    skin=np.array(A.rgb(palette['face']))/255
    out=sample[:,:,:3]*alpha+skin*(1-alpha)
    A.TEX_DIR.mkdir(parents=True,exist_ok=True)
    path=A.TEX_DIR/'techbro_face_cylindrical.png'
    A.Image.fromarray((out*255+.5).astype(np.uint8)).save(path)
    return path


def paint_hair(A,palette):
    pt=A.Painter(1024,A.rgb(palette['hair']),.5,0,ss=2)
    # Deliberate sparse pen marks, not prepainted lighting or dozens of strands.
    for k,x in enumerate([-.34,-.14,.17,.35]):
        pt.stroke([(x*.7,.96),(x,.78),(x*.95,.50),(x*.65,.25),(x*.18,.06)],
                  [.000,.004,.006,.004,0],(42,32,28))
    return pt.save('techbro_hair_flow')


def build_head_mesh(A,C,mats,materials,root,centre,neck,tilt_spec):
    b=C.Builder(mats)
    uv=b.bm.loops.layers.uv.new('UVMap')
    def face(vs,mat,coords=None):
        f=b.bm.faces.new(vs);f.material_index=mats.index(mat)
        if coords:
            for l,q in zip(f.loops,coords): l[uv].uv=q
        return f
    # Dense rings at the nose/lip transitions; face is one continuous surface.
    ys=sorted(set([p[0] for p in SECTIONS]+[-.108+i*.225/36 for i in range(37)]))
    n=64; rings=[]
    for y in ys:
        rings.append([b.bm.verts.new(A.gv(centre+surface(-math.pi+2*math.pi*i/n,y))) for i in range(n)])
    for j in range(len(ys)-1):
        v0=(ys[j]+.115)/.240;v1=(ys[j+1]+.115)/.240
        for i in range(n):
            k=(i+1)%n
            face([rings[j][i],rings[j][k],rings[j+1][k],rings[j+1][i]],'face',[(i/n,v0),((i+1)/n,v0),((i+1)/n,v1),(i/n,v1)])
    face(list(reversed(rings[0])),'skin');face(rings[-1],'skin')
    # Actual neck, ears with inset concha and helix, never texture ears on a plane.
    A.limb(b,'skin',[Vector((0,1.425,-.022)),Vector((0,1.49,-.015)),centre+Vector((0,-.067,-.012))],
           [(.044,.042),(.040,.041),(.043,.041)],sides=20,steps=2)
    for sx in [-1,1]:
        ec=centre+Vector((sx*.081,-.020,-.002))
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
            low=.010+.069*front-.049*back+.004*math.sin(5*a)
            phi=low+(.124-low)*j/R
            rx,zf,zb=interp(min(phi,.117))
            shrink=max(0,(.124-phi)/.007) if phi>.117 else 1
            x=(rx+.009)*math.sin(a)*shrink
            z=((zf+.012)*max(math.cos(a),0)**.55 if math.cos(a)>0 else (zb+.012)*math.cos(a))*shrink
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
    locks=[
      # main sweep over exposed forehead, from left part towards cup side
      ([(-.041,.096,.059),(-.014,.129,.066),(.022,.133,.071),(.058,.105,.083),(.080,.073,.075),(.089,.050,.061)], .029,.013),
      ([(-.046,.099,.039),(-.019,.146,.029),(.031,.149,.032),(.075,.121,.033),(.096,.090,.026),(.094,.063,.010)],.037,.018),
      ([(-.043,.091,.035),(-.058,.117,.045),(-.085,.103,.052),(-.095,.069,.040),(-.096,.047,.022)],.026,.011),
      # forehead curl on the other side of the part
      ([(-.040,.106,.068),(-.012,.114,.088),(.018,.091,.105),(.025,.058,.101),(.037,.034,.085)],.025,.008),
      # Layered diagonal forehead sweep.
      ([(-.052,.105,.050),(-.024,.106,.079),(.006,.079,.111),(.010,.048,.102),(.022,.031,.079)],.016,.006),
      # right temple flow behind ear, two large waves
      ([(.056,.106,.019),(.100,.094,.008),(.106,.061,-.010),(.100,.031,-.022),(.091,.002,-.026)],.032,.014),
      ([(.040,.124,-.047),(.079,.101,-.062),(.098,.066,-.067),(.092,.026,-.064),(.086,-.015,-.039)],.034,.014),
      # left temple, swept back
      ([(-.060,.089,.016),(-.090,.078,.008),(-.102,.051,-.003),(-.096,.023,-.020),(-.081,.003,-.018)],.029,.014),
      ([(-.036,.126,-.043),(-.080,.108,-.054),(-.101,.067,-.060),(-.096,.025,-.059),(-.082,-.013,-.034)],.036,.014),
      ([(-.073,.067,.040),(-.080,.025,.034),(-.078,-.006,.030)],.009,.005),
      ([(.073,.067,.040),(.080,.025,.034),(.078,-.006,.030)],.009,.005),
      # broad back waves
      ([(.008,.132,-.048),(.034,.111,-.091),(.044,.064,-.119),(.040,.008,-.109),(.024,-.040,-.074)],.046,.017),
      ([(-.018,.129,-.054),(-.045,.103,-.092),(-.051,.056,-.117),(-.049,.004,-.107),(-.030,-.038,-.072)],.040,.015),
      # a single restrained lifted wave on crown
      ([(-.010,.114,-.010),(.014,.148,-.013),(.040,.153,-.026),(.063,.139,-.042),(.065,.125,-.056)],.023,.010),
    ]
    for controls,width,depth in locks:
        pts=A.catmull([centre+Vector((p[0],p[1]*.83+.006*A.smoothstep(.10,.15,p[1]),p[2]*(.84 if p[2]>0 else 1))) for p in controls],5)
        rows=[];ns=10
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
    bmesh.ops.scale(b.bm,verts=list(b.bm.verts),vec=Vector((1.15,1,1)))
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
                blend=.92 if abs(q.x)>.018 else .70
                n=n.lerp(tilt@A.gv(stylized),blend).normalized()
        normals.append(n)
    mesh.normals_split_custom_set_from_vertices(normals)
    return obj
