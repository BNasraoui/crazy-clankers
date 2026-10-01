"""Tech Bro v4: open navy fleece, rolled oxford sleeves, khakis and cold brew.

A sculpted sectional head with a cylindrical face atlas and broad swept hair
clumps, posed in relaxed contrapposto. Export plain role materials before adding
preview-only N.L shading and position-merged inverted hulls. Seven transform
nodes; no skeleton. The cup remains under the +X shoulder's arm_R node.

Run build.sh, or blender --background --factory-startup --python techbro.py.
`-- quick` renders the head only without changing the GLB; `-- quick body` also
renders the contact sheet. Full builds always export and render all four files.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mathutils import Vector  # noqa: E402

import anime as A  # noqa: E402
import common as C  # noqa: E402
from anime import g, gv, lerp  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

PALETTE = {
    "skin": 0xF3BE96,
    "face": 0xF3BE96,
    "hair": 0x3C2F29,
    "vest": 0x30374B,
    "shirt": 0xA6BEDF,
    "pants": 0xD4BA94,
    "shoes": 0xF2F2F0,
    "sole": 0xE7E5E0,
    "cup": 0xE4EEF2,
    "coffee": 0x5A3420,
    "straw": 0x222222,
    "ear_ink": 0xB87958,
    "seam": 0x555C68,
    "shoe_panel": 0xCDCFD0,
    "outsole": 0x45484F,
    "ice": 0xB49069,
}
MATS = list(PALETTE)
SMOOTH = 115  # degrees: everything reads as smooth, only real creases stay crisp
TRI_BUDGET = 30000

# --- proportions (game space: Y up, +Z forward, metres) ---------------------------
HEAD_C = Vector((0, 1.625, 0.012))
NECK = Vector((0, 1.44, -0.012))            # head pivot
SHOULDER_R = Vector((0.172, 1.414, -0.014))  # cup arm (+X)
SHOULDER_L = Vector((-0.172, 1.402, -0.014))
HIP_ROLL, SHOULDER_ROLL = 4.0, -4.0          # degrees about Z; +X hip up (weight leg)
PELVIS = Vector((0.038, 0.9, 0.0))
HEAD_TILT = ((4, (0, 0, 1)), (0, (0, 1, 0)), (-12, (1, 0, 0)))  # roll to cup, turn, chin up


def sway(p):
    """Contrapposto: roll each torso slice about Z, interpolating hip to shoulder roll,
    and shift the hips over the standing leg."""
    t = A.smoothstep(0.9, 1.4, p.y)
    r = math.radians(lerp(HIP_ROLL, SHOULDER_ROLL, t))
    cx = lerp(PELVIS.x, 0.0, t)
    return Vector((cx + p.x * math.cos(r), p.y + p.x * math.sin(r), p.z))


def apply(b, fn):
    for v in b.bm.verts:
        v.co = gv(fn(A.to_game(v.co)))


# --- legs ----------------------------------------------------------------------

def leg(b, hip, knee, ankle):
    """Slim chinos: full thigh, narrow knee, a little break above the hem."""
    offset=knee-lerp(hip,ankle,.5)
    pts=[];rad=[]
    for i in range(29):
        t=i/28
        c=lerp(hip+Vector((0,.07,0)),ankle+Vector((0,.006,0)),t)+offset*math.sin(math.pi*t)
        rx=lerp(.085,.055,t)-.005*math.exp(-((t-.55)/.13)**2)
        rz=lerp(.088,.059,t)-.004*math.exp(-((t-.55)/.13)**2)
        ankle_fold=.008*math.exp(-((t-.955)/.027)**2)
        pts.append(c);rad.append((rx+ankle_fold,rz+ankle_fold))
    faces=A.loft(b,"pants",A.path_rings(pts,rad,(0,0,1)),18)
    for v in {v for f in faces for v in f.verts}:
        p=A.to_game(v.co)
        t=max(0,min(1,(hip.y+.07-p.y)/(hip.y+.064-ankle.y)))
        c=lerp(hip+Vector((0,.07,0)),ankle+Vector((0,.006,0)),t)+offset*math.sin(math.pi*t)
        a=math.atan2(p.x-c.x,p.z-c.z)
        # Soft diagonal folds, continuous around the knee instead of ring-shaped cuts.
        fold=.004*math.sin(a*1.5+(p.y-knee.y)*57)*math.exp(-((p.y-knee.y)/.075)**2)
        fold+=.003*math.sin(a*2+(p.y-ankle.y)*92)*math.exp(-((p.y-ankle.y-.04)/.05)**2)
        p.x+=math.sin(a)*fold;p.z+=math.cos(a)*fold;v.co=gv(p)


def shoe(b, ankle, yaw):
    """Chunky sneaker: a hard-edged sole slab, rounded upper with a high heel collar."""
    f = Vector((math.sin(math.radians(yaw)), 0, math.cos(math.radians(yaw))))
    base = Vector((ankle.x, 0, ankle.z))

    def at(t, y):
        return base + f * t + Vector((0, y, 0))
    st = [-0.09, -0.075, -0.02, 0.06, 0.13, 0.175, 0.198]
    sw = [0.032, 0.046, 0.05, 0.057, 0.056, 0.046, 0.026]
    sh = [0.036, 0.036, 0.034, 0.028, 0.026, 0.026, 0.024]
    lift = [0.0, 0.0, 0.0, 0.0, 0.002, 0.006, 0.012]
    rings = A.path_rings([at(t, lift[i] + sh[i] / 2) for i, t in enumerate(st)],
                         [(sw[i] * 1.1, sh[i] / 2) for i in range(len(st))], (0, 1, 0), p=5.0)
    A.loft(b, "sole", rings, 12)
    A.loft(b,"outsole",A.path_rings([at(t,.006+lift[i]) for i,t in enumerate(st)],
        [(sw[i]*1.1,.004) for i in range(len(st))],(0,1,0),p=5.0),12)
    ut = [-0.083, -0.07, -0.02, 0.04, 0.1, 0.15, 0.178]
    uw = [0.034, 0.045, 0.048, 0.052, 0.052, 0.043, 0.026]
    uh = [0.052, 0.06, 0.062, 0.046, 0.033, 0.026, 0.017]
    top = [0.036, 0.036, 0.034, 0.029, 0.027, 0.031, 0.034]
    pts = [at(t, top[i] + uh[i] * 0.85) for i, t in enumerate(ut)]
    rad = [(uw[i] * 1.08, uh[i] * 1.05) for i in range(len(ut))]
    A.loft(b, "shoes", A.path_rings(A.catmull(pts, 2), [r[:2] for r in A.catmull_vals(rad, 2)], (0, 1, 0)),
           12, cap1=at(0.188, 0.036))

    across=Vector((f.z,0,-f.x))
    # Toe cap seam, side panels, tongue and six crossing laces.
    for side in [-1,1]:
        pts=[at(t,y)+across*(side*w) for t,y,w in [(-.067,.060,.048),(.004,.066,.054),(.075,.047,.058),(.144,.040,.045)]]
        A.limb(b,"shoe_panel",pts,[(.006,.003)]*4,sides=6,steps=2)
        pts=[at(t,y)+across*(side*w) for t,y,w in [(-.04,.072,.046),(.005,.061,.050),(.070,.052,.044)]]
        A.limb(b,"seam",pts,[(.009,.003),(.008,.003),(.001,.001)],sides=6,steps=2)
    A.limb(b,"shoe_panel",[at(.005,.156),at(.035,.136),at(.095,.096)],[(.025,.004),(.026,.004),(.020,.003)],sides=8,steps=2)
    for k in range(6):
        t=.040+k*.014;y=.128-k*.009
        A.limb(b,"shoes",[at(t,y)+across*.022,at(t+.008,y+.001),at(t,y)-across*.022],
               [(.0025,.0025)]*3,sides=6,steps=1)


def build_legs():
    b = C.Builder(MATS)
    pel = [(1.0, 0.148, 0.1), (0.93, 0.158, 0.108), (0.87, 0.15, 0.1), (0.81, 0.11, 0.085)]
    rings = [A.ring((0, y, 0), rx, rz, p=2.2) for y, rx, rz in pel]
    A.loft(b, "pants", rings, 20, cap1=Vector((0, 0.77, 0)))
    apply(b, sway)
    # Standing leg (+X, cup side): straight, foot under the hip.
    hip_r = sway(Vector((0.07, 0.86, 0)))
    ankle_r = Vector((0.085, 0.095, -0.01))
    knee_r = lerp(hip_r, ankle_r, 0.5) + Vector((0, 0, 0.012))
    leg(b, hip_r, knee_r, ankle_r)
    shoe(b, ankle_r, 10)
    # Free leg (-X): set out to the side, knee a touch soft.
    hip_l = sway(Vector((-0.07, 0.86, 0)))
    ankle_l = Vector((-0.2, 0.095, 0.035))
    knee_l = A.knee_ik(hip_l, ankle_l, 0.39, 0.39, (0.2, 0, 1))
    leg(b, hip_l, knee_l, ankle_l)
    shoe(b, ankle_l, -14)
    o = b.to_object("legs", MATS_BY_NAME, pivot=g(0, 0.92, 0), parent=ROOT, smooth_angle=SMOOTH)
    A.front_uv(o,"pants",.5,0, fallback=(.01,.99),min_nz=.2)
    A.set_flat(o, {"sole", "outsole"})
    return o


def paint_pants():
    pt=A.Painter(1024,A.rgb(PALETTE["pants"]),.5,0,ss=2)
    ink=(147,125,99)
    folds=[([(.030,.837),(.075,.817),(.127,.817)],[0,.0018,0]),
           ([(.026,.820),(.053,.789),(.066,.749)],[0,.0015,0]),
           ([(-.054,.837),(-.099,.822),(-.124,.802)],[0,.0016,0]),
           ([(.129,.572),(.100,.550),(.068,.514)],[0,.0017,0]),
           ([(-.092,.571),(-.137,.534),(-.158,.522)],[0,.0018,0]),
           ([(.034,.210),(.070,.161),(.130,.138)],[0,.0016,0]),
           ([(-.239,.190),(-.207,.162),(-.164,.147)],[0,.0016,0])]
    for pts,ws in folds: pt.stroke(pts,ws,ink)
    return pt.save('techbro_chino_seams')


# --- torso ---------------------------------------------------------------------
# (y, rx, rz, cz) profiles; superellipse sections.
SHIRT = [(0.872, 0.168, 0.12, 0.0), (0.9, 0.166, 0.118, 0.0), (0.97, 0.162, 0.118, 0.0),
         (1.06, 0.15, 0.106, 0.0), (1.16, 0.15, 0.102, 0.0), (1.26, 0.16, 0.104, 0.0),
         (1.34, 0.168, 0.1, -0.004), (1.4, 0.155, 0.088, -0.008), (1.44, 0.1, 0.07, -0.01),
         (1.47, 0.05, 0.05, -0.012)]
VEST = [(0.955, 0.168, 0.122, 0.0), (0.985, 0.172, 0.127, 0.0), (1.08, 0.167, 0.122, 0.0),
        (1.18, 0.170, 0.116, 0.0), (1.28, 0.177, 0.115, -0.002), (1.36, 0.178, 0.112, -0.006),
        (1.42, 0.166, 0.098, -0.01), (1.465, 0.108, 0.084, -0.012)]


def profile(table, y):
    ys = [r[0] for r in table]
    i = max(1, min(len(ys) - 1, next((k for k, v in enumerate(ys) if v >= y), len(ys) - 1)))
    t = (y - ys[i - 1]) / (ys[i] - ys[i - 1])
    t = t * t * (3 - 2 * t)
    return [lerp(table[i - 1][k], table[i][k], t) for k in (1, 2, 3)]


def section(table, y, a, p=2.3, grow=0.0):
    rx, rz, cz = profile(table, y)
    s, c = math.sin(a), math.cos(a)
    return Vector((math.copysign(abs(s) ** (2 / p), s) * (rx + grow), y,
                   cz + math.copysign(abs(c) ** (2 / p), c) * (rz + grow)))


def opening(y):
    """Half angle (radians) of the open vest front at height y: a narrow gap showing the
    shirt placket, widening into the V under the collar."""
    return math.radians(13 + 22 * A.smoothstep(1.24, 1.465, y))


def collar_base(a):
    d = abs(math.degrees(math.atan2(math.sin(a), math.cos(a))))
    return 1.442 + 0.012 * A.smoothstep(90, 180, d) - 0.05 * A.smoothstep(70, 28, d)


def build_torso():
    b = C.Builder(MATS)
    # Buttoned front with a genuinely open top: the UV placket follows the surface.
    grid=[]
    for j in range(21):
        y=lerp(.872,1.47,j/20)
        a0=.80*A.smoothstep(1.400,1.47,y)
        row=[]
        for i in range(33):
            p=section(SHIRT,y,lerp(a0,2*math.pi-a0,i/32))
            if y<.930:
                front=A.smoothstep(0,.08,p.z)
                p.y+=front*(.036*math.exp(-(p.x/.025)**2)-.013*math.exp(-((abs(p.x)-.067)/.04)**2))
                p.y+=.003*math.sin(p.x*45)
                p.y+=.071*math.exp(-((p.x+.15)/.045)**2)*A.smoothstep(.01,.075,p.z)
            row.append(p)
        grid.append(row)
    A.shell(b,"shirt",grid,.003,wrap=False)
    A.loft(b,"skin",[A.ring((0,1.352,0),.025,.092), A.ring((0,1.40,0),.041,.073),
                     A.ring((0,1.475,-.014),.043,.043)],20)
    # Fleece vest, worn open: a thick shell wrapping from one front edge round the back
    # to the other.
    n, rows = 28, 22
    grid = []
    for j in range(rows + 1):
        y = lerp(0.955, 1.465, j / rows)
        a0 = opening(y)
        row=[section(VEST,y,lerp(a0,2*math.pi-a0,i/(n-1))) for i in range(n)]
        for p in row:
            if y<1.02: p.y+=.012*math.sin(p.x*22)*A.smoothstep(1.02,.95,y)
            radial=Vector((p.x,0,p.z)).normalized()
            front=A.smoothstep(0,.09,p.z)
            ridge=.007*math.exp(-((y-(1.03+.30*abs(p.x)))/.022)**2)
            ridge-=.004*math.exp(-((y-(1.09+.20*abs(p.x)))/.027)**2)
            ridge+=.005*math.exp(-((y-(1.29-.40*abs(p.x)))/.025)**2)
            p+=radial*ridge*front
        grid.append(row)
    A.shell(b, "vest", grid, 0.014, wrap=False, axis=lambda p: Vector((0, p.y, profile(VEST, p.y)[2])))
    # Stand collar: a thick band around the back of the neck, open at the front.
    cn, crows = 26, 4
    cang = [math.radians(lerp(-150, 150, i / (cn - 1))) + math.pi for i in range(cn)]
    cgrid = []
    for j in range(crows + 1):
        s = j / crows
        row = []
        for a in cang:
            d = abs(math.degrees(math.atan2(math.sin(a), math.cos(a))))
            y0 = collar_base(a) - 0.012
            y = lerp(y0, y0 + 0.09 - 0.02 * A.smoothstep(150, 60, d), s)
            r = lerp(1.0, 0.9, s)
            row.append(Vector((math.sin(a) * 0.092 * r, y, -0.014 + math.cos(a) * 0.084 * r)))
        cgrid.append(row)
    A.shell(b, "vest", cgrid, 0.014, wrap=False, axis=lambda p: Vector((0, p.y, -0.014)))
    # Rolled fleece edge down each front.
    for sx in (1, -1):
        ys = [0.958, 1.06, 1.16, 1.26, 1.36, 1.44]
        pts = [section(VEST, y, sx * opening(y), grow=0.002) for y in ys]
        A.limb(b, "vest", pts, [(0.01, 0.012)] * len(pts), sides=8, steps=2)
    # Folded oxford collar: broad base, triangular ends, subtly raised fold.
    for sx in [-1,1]:
        grid=[[Vector((sx*x,y,z)) for x,y,z in row] for row in [
            [(0.018,1.401,.101),(.048,1.391,.098),(.058,1.421,.077)],
            [(0.034,1.435,.071),(.054,1.446,.056),(.068,1.440,.054)]]]
        A.shell(b,"shirt",grid,.004,wrap=False)
    # Armhole binding where the sleeves leave the vest.
    for sx, sh in ((1, SHOULDER_R), (-1, SHOULDER_L)):
        c = Vector((sx * 0.165, sh.y - 0.085, -0.008))
        loop = [c + Vector((sx * 0.012 * math.cos(a), 0.085 * math.sin(a), 0.1 * math.cos(a)))
                for a in (2 * math.pi * k / 16 for k in range(16))]
        rings = A.path_rings(loop, [(0.012, 0.014)] * 16, lambda i, q: q - c, closed=True)
        A.loft(b, "vest", rings, 6, closed=True)
    apply(b, sway)
    o = b.to_object("torso", MATS_BY_NAME, pivot=g(0, 0.95, 0), parent=ROOT, smooth_angle=SMOOTH)
    A.front_uv(o, "vest", VEST_TEX[0], VEST_TEX[1], fallback=(0.01, 0.99), min_nz=0.05)
    A.front_uv(o, "shirt", SHIRT_TEX[0], SHIRT_TEX[1], fallback=(0.01, 0.99), min_nz=0.05)
    return o


VEST_TEX = (0.32, 0.92)  # half size, bottom of the vest texture window


SHIRT_TEX = (0.34, 0.86)


def paint_vest():
    pt = A.Painter(1024, A.rgb(PALETTE["vest"]), *VEST_TEX)
    dark = (22, 27, 44)
    # Chest zip pocket and a small embroidered wordmark on the -X chest (his left in cast.jpg).
    pt.stroke([(-0.08, 1.255), (-0.078, 1.2), (-0.076, 1.16)], [0.004] * 3, dark)
    font=A.ImageFont.load_default(size=round(pt.m(.009)))
    pt.draw.text(pt.px(-.143,1.288),"CORPO",fill=(201,203,210),font=font)
    # Hand-warmer pockets.
    for sx in (1, -1):
        pt.stroke([(sx * .082,1.125),(sx * .095,1.075),(sx * .111,1.015)], [.0025]*3,dark)
        pt.stroke([(sx * .089,1.128),(sx * .135,1.118),(sx * .147,1.017),(sx * .111,1.015)], [0,.0015,.0015,0],dark)
    return pt.save("vest")


def paint_shirt():
    """Button placket down the front, following the contrapposto sway."""
    pt = A.Painter(1024, A.rgb(PALETTE["shirt"]), *SHIRT_TEX)
    line, button = (128, 156, 204), (244, 246, 250)
    ys = [0.86, 1.0, 1.15, 1.3, 1.41]
    for dx in (-0.012, 0.012):
        pt.stroke([(sway(Vector((dx, y, 0))).x, y) for y in ys], [0.0022] * len(ys), line)
    for y in (1.36, 1.27, 1.18, 1.09, 1.0, 0.91):
        x = sway(Vector((0, y, 0))).x
        pt.ellipse(x, y, 0.0055, 0.0055, line)
        pt.ellipse(x, y, 0.0038, 0.0038, button)
    for pts in [[(-.04,1.025),(-.066,1.004),(-.09,.998)],[(.048,.98),(.08,.953),(.12,.939)],
                [(-.025,1.26),(-.042,1.242),(-.06,1.236)]]:
        pt.stroke(pts,[0,.0015,0],line)
    return pt.save("shirt")


# --- head ----------------------------------------------------------------------

from techbro_head import build_head_mesh, paint_head, paint_hair

def build_head():
    return build_head_mesh(A, C, MATS, MATS_BY_NAME, ROOT, HEAD_C, NECK, HEAD_TILT)


# --- arms, hands, cup ------------------------------------------------------------

def sleeve_arm(b, sh, elbow, wrist, roll_at=0.78):
    """Shirt sleeve from the shoulder cap to a rolled cuff on the forearm, bare wrist."""
    up = (elbow - sh).normalized()
    cuff = lerp(elbow, wrist, roll_at)
    pts = [sh - up * 0.02, sh + up * 0.01, lerp(sh, elbow, 0.5), elbow, lerp(elbow, cuff, 0.5), cuff]
    rad = [(0.036, 0.036), (0.058, 0.056), (0.060, 0.057), (0.054, 0.053), (0.050, 0.048), (0.047, 0.046)]
    faces=A.limb(b, "shirt", pts, rad, sides=18, cap0=sh - up * 0.04, cap1="flat", ref=(0, 0, 1))
    for v in {v for f in faces for v in f.verts}:
        p=A.to_game(v.co);d=(p-elbow).length
        p.z+=.006*math.cos((p.y-elbow.y)*92+(p.x-elbow.x)*35)*math.exp(-(d/.078)**2)
        v.co=gv(p)
    fore = (wrist - elbow).normalized()
    A.limb(b, "shirt", [cuff - fore * 0.03, cuff, cuff + fore * 0.02],
           [(0.051, 0.048), (0.055, 0.052), (0.051, 0.048)], sides=16)
    A.limb(b, "skin", [cuff - fore * 0.02, lerp(cuff, wrist, 0.5), wrist],
           [(0.036, 0.034), (0.031, 0.028), (0.026, 0.022)], sides=12, ref=(0, 0, 1))


CUP_C = Vector((0.232, 1.405, 0.118))
CUP_H, CUP_R0, CUP_R1 = 0.135, 0.033, 0.043


def cup_r(y):
    return lerp(CUP_R0, CUP_R1, (y - (CUP_C.y - CUP_H / 2)) / CUP_H)


def around(a_deg, y, extra):
    a = math.radians(a_deg)
    r = cup_r(y) + extra
    return Vector((CUP_C.x + math.sin(a) * r, y, CUP_C.z + math.cos(a) * r))


def cup_hand(b, wrist):
    """Hand gripping the cup: palm on the body side, four fingers wrapped around the
    front, thumb round the back."""
    palm_a = 105
    palm = around(palm_a, CUP_C.y - 0.005, 0.016)
    A.limb(b, "skin", [wrist, lerp(wrist, palm, 0.6), palm],
           [(0.026, 0.02), (0.03, 0.019), (0.034, 0.018)], sides=12,
           ref=lambda i, q: q - Vector((CUP_C.x, q.y, CUP_C.z)), cap1="flat")
    A.blob(b, "skin", palm, (0.034, 0.042, 0.022), rot=A.grot(-palm_a + 90, (0, 1, 0)), u=12, v=8)
    for k, (dy, reach) in enumerate(((0.020, 16), (0.002, 25), (-0.016, 18), (-0.032, 4))):
        y = CUP_C.y + dy
        r = 0.0078 - 0.0008 * (k == 3)
        pts = [around(a, y + 0.004 * math.sin(math.radians(a)), r * 0.9)
               for a in (palm_a - 12, palm_a - 35, 50, 25, reach)]
        A.limb(b, "skin", pts, [(r, r)] * len(pts), sides=8, steps=2, cap1="flat")
    thumb = [around(a, CUP_C.y + 0.03 + 0.01 * i, 0.01) for i, a in enumerate((palm_a - 20, 70, 45, 20))]
    A.limb(b, "skin", thumb, [(0.012, 0.012)] * 4, sides=8, steps=2)


def build_arm_r():
    b = C.Builder(MATS)
    elbow = Vector((0.28, 1.165, -0.03))
    wrist = around(125, CUP_C.y - 0.06, 0.026)
    sleeve_arm(b, SHOULDER_R, elbow, wrist, roll_at=0.46)
    cup_hand(b, wrist)
    o = b.to_object("arm_R", MATS_BY_NAME, pivot=gv(SHOULDER_R), parent=ROOT, smooth_angle=SMOOTH)
    A.fill_uv(o, "shirt", (0.01, 0.99))  # sleeves: plain shirt patch of the texture
    return o


def build_arm_l():
    b = C.Builder(MATS)
    elbow = Vector((-0.25, 1.18, -0.025))
    wrist = Vector((-0.146, 0.974, 0.076))
    sleeve_arm(b, SHOULDER_L, elbow, wrist, roll_at=0.46)
    # Fingers enter the pocket; visible palm and a distinct hooked thumb stay out.
    A.limb(b, "skin", [wrist, Vector((-.121,.955,.069)), Vector((-.105,.925,.040))],
           [(.026,.018),(.029,.017),(.020,.012)], sides=12, steps=2)
    A.limb(b, "skin", [Vector((-.133,.954,.083)),Vector((-.139,.942,.085)),Vector((-.134,.936,.080))],
           [(.011,.009),(.010,.008),(.005,.005)], sides=8,steps=3)
    o = b.to_object("arm_L", MATS_BY_NAME, pivot=gv(SHOULDER_L), parent=ROOT, smooth_angle=SMOOTH)
    A.fill_uv(o, "shirt", (0.01, 0.99))
    return o


def build_cup(parent):
    """Iced cold brew in a clear cup: coffee body, icy band, flat lid, black straw."""
    b = C.Builder(MATS)
    c = CUP_C
    bot = c.y - CUP_H / 2
    y1 = bot + CUP_H * 0.94
    A.loft(b, "coffee", [A.ring((c.x, bot, c.z), CUP_R0, CUP_R0), A.ring((c.x, y1, c.z), cup_r(y1), cup_r(y1))], 20)
    top = bot + CUP_H
    A.loft(b, "cup", [A.ring((c.x, y1, c.z), cup_r(y1) + 0.0005, cup_r(y1) + 0.0005),
                      A.ring((c.x, top, c.z), CUP_R1, CUP_R1)], 20)
    A.loft(b, "cup", [A.ring((c.x, top, c.z), CUP_R1 + 0.004, CUP_R1 + 0.004),
                      A.ring((c.x, top + 0.005, c.z), CUP_R1 + 0.004, CUP_R1 + 0.004),
                      A.ring((c.x, top + 0.008, c.z), CUP_R1 - 0.006, CUP_R1 - 0.006)], 20)
    for dx,dz in [(-.017,.018),(.015,.018),(0,-.012)]:
        A.blob(b,"ice",Vector((c.x+dx,top-.012,c.z+dz)),(.014,.012,.013),u=6,v=4)
    A.limb(b, "straw", [Vector((c.x, top - 0.02, c.z)), Vector((c.x - 0.012, top + 0.1, c.z - 0.01))],
           [(0.0045, 0.0045)] * 2, sides=8, steps=1)
    o = b.to_object("cup", MATS_BY_NAME, pivot=gv(c), parent=parent, smooth_angle=SMOOTH)
    A.set_flat(o, {"cup"})
    return o


# --- build, export, preview ----------------------------------------------------

def export_character():
    import bpy
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(C.MODELS_DIR / "techbro.glb"), export_format="GLB",
        export_yup=True, export_apply=True, export_cameras=False, export_lights=False,
        export_texcoords=True, export_normals=True, export_materials="EXPORT",
        export_animations=False, export_skins=False, export_morph=False)

C.reset_scene()
FACE_PNG = paint_head(A, PALETTE)
VEST_PNG = paint_vest()
MATS_BY_NAME = A.make_materials(PALETTE, {"face": FACE_PNG, "vest": VEST_PNG, "shirt": paint_shirt(), "hair": paint_hair(A, PALETTE), "pants": paint_pants()})
ROOT = C.empty("techbro")
arm_r = build_arm_r()
parts = [build_legs(), build_torso(), build_head(), build_arm_l(), arm_r, build_cup(arm_r)]
C.report(parts)
assert "quick" in ARGS or C.triangle_count(parts) <= TRI_BUDGET, "techbro over its triangle budget"
if "quick" not in ARGS:
    export_character()

pv = A.Preview(ROOT, outline=0.004, shadow_muls={
    "skin": (0.70, 0.49, 0.40), "face": (0.70, 0.49, 0.40), "hair": (0.55, 0.55, 0.7)})
head_c = HEAD_C + Vector((0.015, 0.012, 0))
if "wave" in ARGS:  # the game waves arm_R by rotating it about Z (game) by 2.6 rad
    arm_r.rotation_euler = (0, -2.6, 0)
    pv.sheet("techbro-wave", (("front", 0), ("3/4", -35)), Vector((0, 1.0, 0)), 2.2, 480, aspect=0.7)
    raise SystemExit
pv.sheet("techbro-head", (("front", 0), ("3/4", -35), ("side", -90)), head_c, 0.35, 600)
if "quick" not in ARGS or "body" in ARGS:
    pv.sheet("techbro", (("front", 0), ("3/4", -35), ("side", -90), ("back", 180)),
             Vector((0, 0.9, 0)), 1.95, 720, aspect=0.6)
if "quick" not in ARGS:
    pv.aim(Vector((0, 0.9, 0)), 1.9)
    hero = pv.render(20, 700, 1400)
    A.compare("techbro-compare", C.REPO / "docs/art/cast.jpg", (0, 95, 218, 734), hero, mirror_ref=True,
              labels=("cast.jpg (mirrored for +X cup)", "v5 render"))
    pv.sheet("techbro-small", (("front", 0), ("3/4", -35), ("side", -90), ("back", 180)),
             Vector((0, 0.90, 0)), 2.0, 180, aspect=0.6)
