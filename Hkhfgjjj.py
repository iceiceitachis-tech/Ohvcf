# -*- coding: utf-8 -*-
# ===== เว็บขนส่งในเกม (จำลองสมจริง) =====  เปลี่ยนชื่อไฟล์เป็น app.py แล้วรัน: pip install flask waitress && python app.py
# ระบบเงินทั้งหมดถือเป็นเงินในเกม | เลขบัตร ปชช. เป็นเลขในเกมหรือเลขจริงก็ได้
import os, re, json, time, random, shutil, sqlite3, threading, atexit, datetime, urllib.request
from flask import Flask, request, session, jsonify, Response
from werkzeug.security import generate_password_hash as gh, check_password_hash as ch

# ---------- ตั้งค่า (แก้ได้ตรงนี้) ----------
ADMIN_USER = "1428"
ADMIN_PASSWORD = "iceມຫາ175"      # <<< รหัสแอดมินเริ่มต้น แก้ตรงนี้ (เปลี่ยนในแอปได้ภายหลัง)
PORT = 5000
DB, BK = "data/app.db", "data/backup"
MAX_WH = 6                        # จำกัดคลังสูงสุด 6
os.makedirs(BK, exist_ok=True)

# ---------- ฐานข้อมูล SQLite (WAL) + สำรองอัตโนมัติ ----------
if not os.path.exists(DB):
    fs = sorted(os.listdir(BK))
    if fs: shutil.copy(BK + "/" + fs[-1], DB)   # กู้คืนจากสำรองล่าสุด
L = threading.RLock()
db = sqlite3.connect(DB, check_same_thread=False)
db.execute("pragma journal_mode=wal"); db.execute("pragma synchronous=full")
db.execute("create table if not exists d(k text,i text,v text,primary key(k,i))"); db.commit()

def put(k, i, o):
    with L:
        db.execute("replace into d values(?,?,?)", (k, str(i), json.dumps(o, ensure_ascii=False))); db.commit()
def get(k, i):
    r = db.execute("select v from d where k=? and i=?", (k, str(i))).fetchone()
    return json.loads(r[0]) if r else None
def al(k): return [json.loads(r[0]) for r in db.execute("select v from d where k=? order by rowid", (k,))]
def rm(k, i):
    with L: db.execute("delete from d where k=? and i=?", (k, str(i))); db.commit()
def backup():
    with L:
        b = sqlite3.connect(BK + "/app_" + time.strftime("%Y%m%d_%H%M%S") + ".db"); db.backup(b); b.close()
    fs = sorted(os.listdir(BK))
    for x in fs[:-30]: os.remove(BK + "/" + x)
def bkloop():
    while True: time.sleep(300); backup()
threading.Thread(target=bkloop, daemon=True).start(); atexit.register(backup)

if not get("u", ADMIN_USER):
    put("u", ADMIN_USER, {"username": ADMIN_USER, "first": "ผู้ดูแล", "last": "ระบบ", "role": "admin", "pw": gh(ADMIN_PASSWORD), "av": "", "phone": ""})
if not get("s", "cfg"): put("s", "cfg", {"name": "ส่งมาให้ขน", "logo": "", "theme": "yo"})
if not get("s", "home"): put("s", "home", {"media": [], "items": []})

# ---------- ตัวช่วย ----------
app = Flask(__name__)
if not os.path.exists("data/key"): open("data/key", "w").write(os.urandom(24).hex())
app.secret_key = open("data/key").read()
app.config["MAX_CONTENT_LENGTH"] = 64 * 2 ** 20
class X(Exception): pass
def now(): return datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
def log(w, t): put("log", time.time_ns(), {"t": now(), "w": w, "x": t})
def note(u, t):
    i = str(time.time_ns()); put("n", i, {"id": i, "u": u, "t": now(), "x": t})
def pub(u): return {k: v for k, v in u.items() if k != "pw"}
def need(u, *r):
    if not u or u["role"] not in r: raise X("ไม่มีสิทธิ์ใช้งาน")
def req(d, *ks):
    for k in ks:
        if not str(d.get(k, "")).strip(): raise X("กรุณากรอกข้อมูลให้ครบ", k)
def nid(s):
    if not re.fullmatch("[0-9]{13}", str(s)): raise X("เลขบัตรประชาชนต้องเป็นเลขอารบิก 13 หลักเท่านั้น", "nid")
PHK = ("sphoto", "pphoto", "whp", "dph")
def lite(p): return {k: v for k, v in p.items() if k not in PHK}
def up(p, x, loc=None): p["ups"].append({"t": now(), "x": x, "loc": loc or []})
def sv(p, u, txt, st=None, loc=None):
    if st: p["status"] = st
    up(p, txt, loc); put("p", p["no"], p)
    note(p["owner"], "พัสดุ %s: %s" % (p["no"], txt)); log(u["username"], "พัสดุ %s: %s" % (p["no"], txt))
def mp(d, u, *st):
    need(u, "courier"); p = get("p", d.get("no"))
    if not p or p.get("courier") != u["username"] or p["status"] not in st: raise X("สถานะพัสดุไม่ถูกต้อง")
    return p

# ---------- ฐานชื่อสถานที่ไทย (เพิ่มได้เรื่อยๆ รูปแบบ ชื่อ,lat,lng) ----------
GZ = "กรุงเทพ,13.7563,100.5018;บางจาก,13.6960,100.6010;บางนา,13.6680,100.6050;ลาดพร้าว,13.8050,100.6100;รังสิต,13.9870,100.6170;นนทบุรี,13.8621,100.5144;ปทุมธานี,14.0208,100.5250;สมุทรปราการ,13.5991,100.5998;สมุทรสาคร,13.5475,100.2744;สมุทรสงคราม,13.4098,100.0023;นครปฐม,13.8199,100.0443;พระนครศรีอยุธยา,14.3532,100.5684;อ่างทอง,14.5896,100.4550;สิงห์บุรี,14.8936,100.3967;ชัยนาท,15.1851,100.1251;ลพบุรี,14.7995,100.6534;สระบุรี,14.5289,100.9101;นครนายก,14.2069,101.2131;ฉะเชิงเทรา,13.6904,101.0780;ปราจีนบุรี,14.0509,101.3727;สระแก้ว,13.8240,102.0646;ชลบุรี,13.3611,100.9847;พัทยา,12.9236,100.8825;ระยอง,12.6814,101.2816;จันทบุรี,12.6114,102.1039;ตราด,12.2428,102.5175;ราชบุรี,13.5283,99.8134;กาญจนบุรี,14.0228,99.5328;สุพรรณบุรี,14.4745,100.1177;เพชรบุรี,13.1119,99.9447;หัวหิน,12.5684,99.9577;ประจวบคีรีขันธ์,11.8124,99.7973;ชุมพร,10.4930,99.1800;ระนอง,9.9528,98.6085;สุราษฎร์ธานี,9.1382,99.3217;นครศรีธรรมราช,8.4304,99.9631;กระบี่,8.0863,98.9063;พังงา,8.4509,98.5255;ภูเก็ต,7.8804,98.3923;ตรัง,7.5563,99.6114;พัทลุง,7.6167,100.0774;สงขลา,7.1897,100.5954;หาดใหญ่,7.0086,100.4747;สตูล,6.6238,100.0674;ปัตตานี,6.8696,101.2501;ยะลา,6.5413,101.2804;นราธิวาส,6.4255,101.8253;นครราชสีมา,14.9799,102.0977;บุรีรัมย์,14.9930,103.1029;สุรินทร์,14.8820,103.4937;ศรีสะเกษ,15.1186,104.3220;อุบลราชธานี,15.2287,104.8564;ยโสธร,15.7921,104.1453;ชัยภูมิ,15.8068,102.0316;ขอนแก่น,16.4322,102.8236;มหาสารคาม,16.1851,103.3027;ร้อยเอ็ด,16.0538,103.6520;กาฬสินธุ์,16.4314,103.5059;อุดรธานี,17.4138,102.7870;หนองคาย,17.8782,102.7413;สกลนคร,17.1545,104.1348;นครพนม,17.4108,104.7783;มุกดาหาร,16.5420,104.7235;เลย,17.4860,101.7223;เชียงใหม่,18.7883,98.9853;เชียงราย,19.9105,99.8406;ลำปาง,18.2888,99.4908;ลำพูน,18.5745,99.0087;แพร่,18.1445,100.1403;น่าน,18.7756,100.7730;พะเยา,19.1665,99.9019;แม่ฮ่องสอน,19.3020,97.9654;อุตรดิตถ์,17.6200,100.0993;สุโขทัย,17.0056,99.8264;พิษณุโลก,16.8211,100.2659;พิจิตร,16.4429,100.3487;เพชรบูรณ์,16.4190,101.1606;ตาก,16.8840,99.1259;แม่สอด,16.7158,98.5714;กำแพงเพชร,16.4828,99.5227;นครสวรรค์,15.7047,100.1372;อุทัยธานี,15.3792,100.0245"
PL = sorted([(a, float(b), float(c)) for a, b, c in (x.split(",") for x in GZ.split(";"))], key=lambda x: -len(x[0]))
def locs(t): return [[n, a, b] for n, a, b in PL if n in t]

# ---------- API (ทุกคำสั่งผ่าน POST /api) ----------
H = {}
def h(f): H[f.__name__] = f; return f

@app.post("/api")
def api():
    d = request.get_json(force=True) or {}; a = d.pop("a", ""); u = get("u", session["u"]) if session.get("u") else None
    f = H.get(a)
    if not f: return jsonify({"err": "ไม่พบคำสั่ง"})
    try:
        with L: return jsonify(f(d, u))
    except X as e: return jsonify({"err": e.args[0], "field": e.args[1] if len(e.args) > 1 else None})
    except Exception as e: return jsonify({"err": "ผิดพลาด: " + str(e)})

@h
def cfg(d, u): return {"cfg": get("s", "cfg"), "me": pub(u) if u else None}
@h
def logout(d, u): session.clear(); return {"ok": 1}
@h
def login(d, u):
    x = get("u", str(d.get("username", "")))
    if not x or not ch(x["pw"], str(d.get("password", ""))): raise X("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    session["u"] = x["username"]; log(x["username"], "เข้าสู่ระบบ"); return {"ok": 1}

@h
def reg_member(d, u):
    req(d, "first", "last", "phone", "birth", "nid", "username", "password"); nid(d["nid"])
    if get("u", d["username"].strip()): raise X("ชื่อผู้ใช้นี้ถูกใช้แล้ว", "username")
    o = {k: str(d[k]).strip() for k in ("first", "last", "phone", "birth", "nid", "username")}
    o.update(role="member", pw=gh(d["password"]), t=now(), av="")
    put("u", o["username"], o); session["u"] = o["username"]; log(o["username"], "สมัครสมาชิก"); return {"ok": 1}

@h
def reg_courier(d, u):
    req(d, "first", "last", "username", "password", "phone", "nid", "addr", "id_f", "id_b", "birth"); nid(d["nid"])
    if get("u", d["username"].strip()): raise X("ชื่อผู้ใช้นี้ถูกใช้แล้ว", "username")
    o = {k: str(d[k]).strip() for k in ("first", "last", "phone", "birth", "nid", "username", "addr")}
    o.update(role="member", pw=gh(d["password"]), t=now(), av="", req={"id_f": d["id_f"], "id_b": d["id_b"], "t": now()})
    put("u", o["username"], o); session["u"] = o["username"]; log(o["username"], "สมัครพนักงานขนส่ง (รออนุมัติ)"); return {"ok": 1}

@h
def chpw(d, u):
    need(u, "member", "courier", "wh", "admin"); req(d, "old", "new")
    if not ch(u["pw"], d["old"]): raise X("รหัสปัจจุบันไม่ถูกต้อง", "old")
    if len(d["new"]) < 4: raise X("รหัสใหม่ต้องมีอย่างน้อย 4 ตัว", "new")
    u["pw"] = gh(d["new"]); put("u", u["username"], u); log(u["username"], "เปลี่ยนรหัสผ่าน"); return {"ok": 1}

@h
def set_av(d, u):
    need(u, "member", "courier", "wh", "admin"); req(d, "av"); u["av"] = d["av"]; put("u", u["username"], u); return {"ok": 1}

# --- หน้าหลัก ---
@h
def home_get(d, u): return get("s", "home")
@h
def home_media(d, u):
    need(u, "admin"); req(d, "media"); x = get("s", "home"); x["media"].append(d["media"]); put("s", "home", x); log(u["username"], "เพิ่มรูป/วีดีโอหน้าหลัก"); return {"ok": 1}
@h
def home_mdel(d, u):
    need(u, "admin"); x = get("s", "home"); x["media"].pop(int(d["i"])); put("s", "home", x); log(u["username"], "ลบรูป/วีดีโอหน้าหลัก"); return {"ok": 1}
@h
def home_add(d, u):
    need(u, "admin"); req(d, "title", "detail"); x = get("s", "home")
    x["items"].append({"id": str(time.time_ns()), "title": d["title"], "detail": d["detail"]}); put("s", "home", x); log(u["username"], "เพิ่มข้อความหน้าหลัก: " + d["title"]); return {"ok": 1}
@h
def home_del(d, u):
    need(u, "admin"); x = get("s", "home"); x["items"] = [i for i in x["items"] if i["id"] != d["id"]]; put("s", "home", x); log(u["username"], "ลบข้อความหน้าหลัก"); return {"ok": 1}

# --- พัสดุ ---
@h
def send(d, u):
    need(u, "member"); req(d, "sname", "saddr", "sphone", "sphoto", "pphoto", "rname", "rphone", "raddr")
    for f in al("fake"):
        if f["x"] and (f["x"] in d["raddr"] or f["x"] in d["saddr"]): raise X("ที่อยู่นี้อยู่ในรายการที่อยู่ปลอม ส่งไม่ได้", "raddr")
    while True:
        no = "TH" + "".join(random.choices("0123456789", k=10))
        if not get("p", no): break
    p = {k: d.get(k, "") for k in ("sname", "saddr", "sphone", "sphoto", "pphoto", "rname", "rphone", "raddr", "gps")}
    p.update(no=no, owner=u["username"], oname=u["first"] + " " + u["last"], status="wait", courier=None, t=now(), ups=[])
    up(p, "สร้างพัสดุ รอพนักงานรับงาน"); put("p", no, p)
    note(u["username"], "สร้างพัสดุสำเร็จ เลขพัสดุ %s" % no); log(u["username"], "สร้างพัสดุ " + no); return {"no": no}
@h
def p_list(d, u):
    need(u, "member"); return [lite(p) for p in al("p") if p["owner"] == u["username"]][::-1]
@h
def track(d, u):
    need(u, "member", "courier", "wh", "admin"); p = get("p", str(d.get("no", "")).strip())
    if not p: raise X("ไม่พบเลขพัสดุนี้")
    if u["role"] == "member" and p["owner"] != u["username"]: raise X("ไม่พบเลขพัสดุนี้")
    c = get("u", p.get("courier") or "")
    return {"p": p, "c": {"n": c["first"] + " " + c["last"], "ph": c.get("phone", "")} if c else None}
@h
def jobs(d, u):
    need(u, "courier"); return [lite(p) for p in al("p") if p["status"] in ("wait", "ready")]
@h
def mine(d, u):
    need(u, "courier"); return [lite(p) for p in al("p") if p.get("courier") == u["username"] and p["status"] in ("pick", "got", "deliv")]
@h
def accept(d, u):
    need(u, "courier"); p = get("p", d.get("no"))
    if not p or p["status"] not in ("wait", "ready"): raise X("งานนี้ถูกรับไปแล้ว")
    p["courier"] = u["username"]
    if p["status"] == "wait": sv(p, u, "พนักงานกำลังไปรับพัสดุที่หน้าบ้านผู้ส่ง", "pick")
    else: sv(p, u, "พนักงานรับพัสดุแล้ว กำลังนำส่งถึงผู้รับ", "deliv")
    return {"ok": 1}
@h
def pickup(d, u):
    p = mp(d, u, "pick"); req(d, "weight", "fee", "cod")
    if d["cod"] not in ("ปลายทาง", "จ่ายที่จุดรับ", "ไม่มีเก็บเงินปลายทาง"): raise X("ช่องทางเก็บเงินไม่ถูกต้อง", "cod")
    p.update(weight=d["weight"], fee=d["fee"], cod=d["cod"]); sv(p, u, "พนักงานรับพัสดุแล้ว (น้ำหนัก %s กก. ค่าขนส่ง %s เงินในเกม, %s)" % (d["weight"], d["fee"], d["cod"]), "got"); return {"ok": 1}
@h
def upd(d, u):
    p = mp(d, u, "pick", "got", "deliv"); req(d, "text"); sv(p, u, d["text"].strip(), None, locs(d["text"])); return {"ok": 1}
@h
def drop_wh(d, u):
    p = mp(d, u, "got"); req(d, "wh", "ph1", "ph2", "ph3")
    if not get("u", d["wh"]): raise X("ไม่พบคลังนี้", "wh")
    p["whn"] = d["wh"]; p["whp"] = [d["ph1"], d["ph2"], d["ph3"]]; sv(p, u, "พนักงานส่งพัสดุที่คลัง " + d["wh"], "wh"); p["courier"] = None; put("p", p["no"], p); return {"ok": 1}
@h
def deliver(d, u):
    p = mp(d, u, "deliv"); req(d, "ph1", "ph2", "ph3")
    p["dph"] = [d["ph1"], d["ph2"], d["ph3"]]; p["done"] = now(); sv(p, u, "จัดส่งพัสดุสำเร็จ", "done"); return {"ok": 1}

# --- คลัง ---
@h
def whs(d, u): return [x["username"] for x in al("u") if x["role"] == "wh"]
@h
def wh_list(d, u): need(u, "wh"); return [lite(p) for p in al("p") if p["status"] in ("wh", "van", "ready")]
@h
def wh_step(d, u):
    need(u, "wh"); p = get("p", d.get("no"))
    if not p or p["status"] not in ("wh", "van"): raise X("สถานะไม่ถูกต้อง")
    if p["status"] == "wh": sv(p, u, "คลังนำพัสดุขึ้นรถ กำลังเดินทางไปคลังปลายทาง", "van")
    else: sv(p, u, "พัสดุถึงคลังปลายทางแล้ว เปิดให้พนักงานรับงานนำส่ง", "ready")
    return {"ok": 1}
@h
def pend(d, u): need(u, "wh", "admin"); return [pub(x) for x in al("u") if x.get("req")]
@h
def c_do(d, u):
    need(u, "wh", "admin"); x = get("u", d.get("username"))
    if not x or not x.get("req"): raise X("ไม่พบคำขอ")
    if d.get("ok"): x["role"] = "courier"; note(x["username"], "คำขอสมัครพนักงานขนส่งได้รับการอนุมัติแล้ว กรุณาเข้าสู่ระบบใหม่"); log(u["username"], "อนุมัติพนักงาน " + x["username"])
    else: note(x["username"], "คำขอสมัครพนักงานขนส่งถูกปฏิเสธ"); log(u["username"], "ปฏิเสธพนักงาน " + x["username"])
    x.pop("req"); put("u", x["username"], x); return {"ok": 1}

# --- แจ้งเตือน ---
@h
def nts(d, u): need(u, "member", "courier", "wh", "admin"); return [n for n in al("n") if n["u"] == u["username"]][::-1]
@h
def dn(d, u):
    need(u, "member", "courier", "wh", "admin"); n = get("n", d.get("id"))
    if n and n["u"] == u["username"]: rm("n", n["id"])
    return {"ok": 1}

# --- โปรไฟล์ (ขอแก้ไข -> แอดมินอนุมัติ) ---
@h
def edit_req(d, u):
    need(u, "member", "courier"); req(d, "first", "last", "phone", "birth", "nid"); nid(d["nid"])
    put("er", u["username"], {"username": u["username"], "t": now(), **{k: str(d[k]).strip() for k in ("first", "last", "phone", "birth", "nid")}})
    log(u["username"], "ขอแก้ไขข้อมูลโปรไฟล์"); return {"ok": 1}
@h
def er_list(d, u): need(u, "admin"); return al("er")
@h
def er_do(d, u):
    need(u, "admin"); e = get("er", d.get("username")); x = get("u", d.get("username"))
    if not e or not x: raise X("ไม่พบคำขอ")
    if d.get("ok"):
        for k in ("first", "last", "phone", "birth", "nid"): x[k] = e[k]
        put("u", x["username"], x); note(x["username"], "การแก้ไขข้อมูลโปรไฟล์ได้รับการอนุมัติเรียบร้อย"); log(u["username"], "อนุมัติแก้ไขข้อมูล " + x["username"])
    else: note(x["username"], "การแก้ไขข้อมูลโปรไฟล์ถูกปฏิเสธ"); log(u["username"], "ปฏิเสธแก้ไขข้อมูล " + x["username"])
    rm("er", e["username"]); return {"ok": 1}

# --- แอดมิน ---
@h
def users(d, u): need(u, "admin"); return [pub(x) for x in al("u") if x["role"] != "admin"]
@h
def u_edit(d, u):
    need(u, "admin"); x = get("u", d.get("username"))
    if not x or d.get("f") not in ("first", "last", "phone"): raise X("แก้ไขไม่ได้")
    x[d["f"]] = d["v"]; put("u", x["username"], x); log(u["username"], "แก้ไข %s ของ %s" % (d["f"], x["username"])); return {"ok": 1}
@h
def u_del(d, u):
    need(u, "admin")
    if d.get("username") == ADMIN_USER: raise X("ลบแอดมินไม่ได้")
    rm("u", d.get("username")); log(u["username"], "ลบผู้ใช้ " + str(d.get("username"))); return {"ok": 1}
@h
def done_list(d, u): need(u, "admin"); return [p for p in al("p") if p["status"] == "done"][::-1]
@h
def p_edit(d, u):
    need(u, "admin"); p = get("p", d.get("no"))
    if not p or d.get("f") not in ("sname", "sphone", "saddr", "rname", "rphone", "raddr"): raise X("แก้ไขไม่ได้")
    p[d["f"]] = d["v"]; put("p", p["no"], p); log(u["username"], "แก้ไขพัสดุ %s (%s)" % (p["no"], d["f"])); return {"ok": 1}
@h
def p_del(d, u): need(u, "admin"); rm("p", d.get("no")); log(u["username"], "ลบพัสดุ " + str(d.get("no"))); return {"ok": 1}
@h
def add_wh(d, u):
    need(u, "admin"); req(d, "username", "password")
    if len([1 for x in al("u") if x["role"] == "wh"]) >= MAX_WH: raise X("เพิ่มคลังได้สูงสุด %d คลังเท่านั้น" % MAX_WH)
    if get("u", d["username"]): raise X("ชื่อผู้ใช้นี้ถูกใช้แล้ว", "username")
    put("u", d["username"], {"username": d["username"], "first": d["username"], "last": "(คลัง)", "role": "wh", "pw": gh(d["password"]), "av": "", "phone": ""})
    log(u["username"], "เพิ่มคลังสินค้า " + d["username"]); return {"ok": 1}
@h
def set_cfg(d, u):
    need(u, "admin"); c = get("s", "cfg")
    if d.get("theme") and d["theme"] != c["theme"]:
        if not ch(u["pw"], str(d.get("apw", ""))): raise X("ต้องใส่รหัสแอดมินให้ถูกต้องก่อนเปลี่ยนโทนสี", "apw")
        c["theme"] = d["theme"]
    if d.get("name"): c["name"] = d["name"].strip()
    if d.get("logo"): c["logo"] = d["logo"]
    put("s", "cfg", c); log(u["username"], "แก้ไขการตั้งค่าแอป (ชื่อ/โลโก้/โทนสี)"); return {"ok": 1}
@h
def logs(d, u): need(u, "admin"); return al("log")[::-1][:500]
@h
def fake_list(d, u): need(u, "admin"); return al("fake")
@h
def fake_add(d, u):
    need(u, "admin"); n = 0
    if d.get("url"):
        url = d["url"].strip().replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        txt = urllib.request.urlopen(url, timeout=15).read().decode("utf-8", "ignore")
    else: txt = d.get("text", "")
    items = re.findall(r"\[(.*?)\]", txt, re.S) or txt.split("\n")
    for x in items:
        x = x.strip().strip(",").strip()
        if x: put("fake", str(time.time_ns()), {"id": str(time.time_ns()), "x": x}); n += 1; time.sleep(0.000001)
    log(u["username"], "เพิ่มที่อยู่ปลอม %d รายการ" % n); return {"n": n}
@h
def fake_del(d, u): need(u, "admin"); rm("fake", d.get("id")); log(u["username"], "ลบที่อยู่ปลอม"); return {"ok": 1}

# ---------- หน้าเว็บ ----------
@app.get("/")
def index(): return Response(PAGE, mimetype="text/html")

PAGE = r'''<!doctype html><html lang=th><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>app</title><link rel=stylesheet href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--p:#f59e0b;--q:#f97316;--bg:#fff8ec}
[data-t=bl]{--p:#0ea5e9;--q:#2563eb;--bg:#eff8ff}[data-t=ro]{--p:#f97316;--q:#dc2626;--bg:#fff3ec}[data-t=rw]{--p:#dc2626;--q:#991b1b;--bg:#fff}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);padding-bottom:70px}
header{background:linear-gradient(90deg,var(--p),var(--q));color:#fff;padding:12px 16px;display:flex;gap:10px;align-items:center;position:sticky;top:0;z-index:5}header img{width:34px;height:34px;border-radius:50%;object-fit:cover}
#app{padding:12px;max-width:720px;margin:auto}nav{position:fixed;bottom:0;left:0;right:0;display:flex;background:#fff;border-top:2px solid var(--p);z-index:5}
nav a{flex:1;text-align:center;padding:6px 2px;font-size:11px;color:#555}nav a.on{color:var(--q);font-weight:700}nav a span{display:block;font-size:20px}
.card{background:#fff;border-radius:12px;margin:8px 0;box-shadow:0 1px 4px #0002;overflow:hidden}.h{padding:12px;display:flex;justify-content:space-between;align-items:center;gap:6px;cursor:pointer}.b{display:none;padding:0 12px 12px;font-size:14px;word-break:break-word}.b.o{display:block}
button{border:0;border-radius:8px;padding:8px 12px;background:#eee;font-size:14px;margin:2px}button.pr{background:linear-gradient(90deg,var(--p),var(--q));color:#fff}button.dg{background:#dc2626;color:#fff}
label{display:block;margin:8px 0;font-size:13px}input,select,textarea{width:100%;padding:9px;border:1px solid #ccc;border-radius:8px;font-size:15px}input.bad{border-color:red;background:#fee}
.r{display:flex;gap:6px}#m{position:fixed;inset:0;background:#0007;display:none;align-items:center;justify-content:center;z-index:20}.mb{background:#fff;border-radius:14px;padding:16px;width:92%;max-width:440px;max-height:88vh;overflow:auto}
.wel{text-align:center;padding:40px 10px}.big{font-size:90px}.big img{width:120px;height:120px;border-radius:50%}.wel button{font-size:18px;padding:14px 30px}.sm{margin-top:24px;font-size:13px}.sm a{color:var(--q);text-decoration:underline}
#toast{position:fixed;top:60px;left:50%;transform:translateX(-50%);background:#222;color:#fff;padding:10px 16px;border-radius:10px;display:none;z-index:30;max-width:90%}
#map{height:260px;border-radius:12px;margin-bottom:8px}img.t{width:80px;height:80px;object-fit:cover;border-radius:8px;margin:2px}video,.b img.w{max-width:100%;border-radius:10px;margin:6px 0}
.nt{touch-action:pan-y;display:flex;justify-content:space-between;align-items:center}.nt .del{display:none;background:#dc2626;color:#fff}.nt.sw .del{display:inline}.c{text-align:center;color:#777}
.st{border-left:3px solid var(--p);padding:4px 10px;margin:6px 0;font-size:14px}input[type=range]{padding:0}
</style></head><body><header id=hd></header><div id=app></div><nav id=nav></nav><div id=m></div><div id=toast></div>
<script>
const TH=['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'];
const ST={wait:'รอพนักงานรับพัสดุ',pick:'พนักงานกำลังไปรับพัสดุ',got:'พนักงานรับพัสดุแล้ว',wh:'อยู่ที่คลัง',van:'อยู่ระหว่างขนส่งระหว่างคลัง',ready:'ถึงคลังปลายทาง รอพนักงานรับ',deliv:'กำลังนำส่ง',done:'จัดส่งสำเร็จ'};
const $=s=>document.querySelector(s);let ME=null,CFG={},TAB='',PH={},AFTER=null,DET=null,SUB='',sx=0;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function toast(t){const e=$('#toast');e.textContent=t;e.style.display='block';clearTimeout(window.tt);window.tt=setTimeout(()=>e.style.display='none',3500)}
async function api(a,d={}){try{const r=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({a,...d})});const j=await r.json();
 if(j&&j.err){toast(j.err);if(j.field){const e=document.querySelector('#f [name='+j.field+']');if(e){e.value='';e.classList.add('bad');e.focus()}}return null}return j}catch(e){toast('เชื่อมต่อไม่ได้');return null}}
function fld(n,l,t='text',o=[],v=''){
 if(t=='sel')return `<label>${l}<select name=${n}>${o.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label>`;
 if(t=='ph'||t=='cam')return `<label>${l}<input type=file name=${n} accept="image/*" ${t=='cam'?'capture':''} onchange="pick(this)"></label>`;
 if(t=='ta')return `<label>${l}<textarea name=${n} rows=5></textarea></label>`;
 if(t=='birth'){const y=[];for(let i=2569;i>=2440;i--)y.push(i);return `<label>${l}<div class=r><select name=bd>${Array.from({length:31},(_,i)=>`<option>${i+1}</option>`)}</select><select name=bm>${TH.map(x=>`<option>${x}</option>`)}</select><select name=by>${y.map(x=>`<option>${x}</option>`)}</select></div></label>`}
 const x=n=='nid'?' maxlength=13 inputmode=numeric oninput="this.value=this.value.replace(/[^0-9]/g,\'\')"':'';
 return `<label>${l}<input name=${n} type=${t} value="${esc(v)}"${x}></label>`}
function V(){const o={};document.querySelectorAll('#f [name]').forEach(e=>{o[e.name]=e.type=='file'?(PH[e.name]||''):e.value});if(o.bd)o.birth=o.bd+' '+o.bm+' '+o.by;return o}
function pick(e){const f=e.files[0];if(!f)return;const r=new FileReader();
 if(f.type.startsWith('video')){if(f.size>15e6){toast('วีดีโอใหญ่เกิน 15MB');return}r.onload=()=>PH[e.name]=r.result;r.readAsDataURL(f);return}
 r.onload=()=>{const i=new Image();i.onload=()=>{const c=document.createElement('canvas'),k=Math.min(1,700/Math.max(i.width,i.height));c.width=i.width*k;c.height=i.height*k;c.getContext('2d').drawImage(i,0,0,c.width,c.height);PH[e.name]=c.toDataURL('image/jpeg',.7)};i.src=r.result};r.readAsDataURL(f)}
function M(t,fs,ok,lb='ตกลง'){PH={};$('#m').innerHTML=`<div class=mb><h3>${t}</h3><div id=f>${fs}</div><div class=r><button onclick=X()>ยกเลิก</button><button class=pr id=okb>${lb}</button></div></div>`;$('#m').style.display='flex';$('#okb').onclick=()=>ok(V())}
function X(){$('#m').style.display='none';$('#m').innerHTML=''}
function zoom(s){$('#m').innerHTML=`<img src="${s}" style="max-width:96%;max-height:92vh" onclick=X()>`;$('#m').style.display='flex'}
const row=(t,b,a='')=>`<div class=card><div class=h onclick="this.nextElementSibling.classList.toggle('o')"><b>${t}</b><span>${a}</span></div><div class=b>${b}</div></div>`;
const bt=(js,l,c='')=>`<button class="${c}" onclick="event.stopPropagation();${js}">${l}</button>`;
const imgs=a=>(a||[]).map(s=>`<img class=t src="${s}" onclick=zoom(this.src)>`).join('');
const cf=m=>confirm(m||'ยืนยันการลบ? ลบแล้วกู้คืนไม่ได้');
const rl=r=>({member:'สมาชิก',courier:'พนักงานขนส่ง',wh:'คลัง',admin:'แอดมิน'}[r]);
function map(pts,gps){const m=L.map('map').setView([13.0,101.0],5);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(m);const b=[];
 pts.forEach((p,i)=>{L.marker([p[1],p[2]]).addTo(m).bindPopup(p[0]);b.push([p[1],p[2]])});
 if(gps){const g=gps.split(',').map(Number);if(g.length==2&&!isNaN(g[0])&&!isNaN(g[1])){L.circleMarker(g,{color:'red'}).addTo(m).bindPopup('ตำแหน่งผู้รับ');b.push(g)}}
 if(b.length)m.fitBounds(b,{maxZoom:11,padding:[30,30]})}
const NAV={member:[['home','🏠','หน้าหลัก'],['my','📦','พัสดุของฉัน'],['send','✉️','ส่งพัสดุ'],['nt','🔔','แจ้งเตือน'],['pf','👤','โปรไฟล์']],
 courier:[['jobs','📋','รับงาน'],['mine','🚚','งานของฉัน'],['pf','👤','โปรไฟล์'],['nt','🔔','แจ้งเตือน']],
 wh:[['whp','🏭','พัสดุคลัง'],['ap','✅','อนุมัติพนักงาน'],['nt','🔔','แจ้งเตือน'],['pw','🔑','รหัส']],
 admin:[['ad','⚙️','จัดการ'],['nt','🔔','แจ้งเตือน'],['pw','🔑','รหัส']]};
async function boot(){const r=await api('cfg');if(!r)return;CFG=r.cfg;ME=r.me;document.documentElement.dataset.t=CFG.theme;document.title=CFG.name;
 if(!ME)TAB='wel';else if(!TAB||TAB=='wel')TAB={member:'home',courier:'jobs',wh:'whp',admin:'ad'}[ME.role];draw()}
async function draw(){$('#hd').innerHTML=(CFG.logo?`<img src="${CFG.logo}">`:'🚚 ')+`<b>${esc(CFG.name)}</b>`;
 $('#nav').innerHTML=ME?NAV[ME.role].map(n=>`<a class="${n[0]==TAB?'on':''}" onclick="TAB='${n[0]}';SUB='';draw()"><span>${n[1]}</span>${n[2]}</a>`).join(''):'';
 AFTER=null;$('#app').innerHTML='<p class=c>กำลังโหลด...</p>';$('#app').innerHTML=await V_[TAB]();if(AFTER)AFTER()}
const V_={};
V_.wel=()=>`<div class=wel><div class=big>${CFG.logo?`<img src="${CFG.logo}">`:'🛵'}</div><h1>สวัสดี!</h1><p>ยินดีต้อนรับสู่ ${esc(CFG.name)}</p><button class=pr onclick=regM()>เข้าสู่เว็บไซต์</button><div class=sm><a onclick=regC()>สมัครพนักงาน</a> · <a onclick=logM()>เข้าสู่ระบบ</a></div></div>`;
function regM(){M('สมัครสมาชิก',fld('first','ชื่อ')+fld('last','นามสกุล')+fld('phone','เบอร์ติดต่อ','tel')+fld('birth','วันเกิด','birth')+fld('nid','เลขบัตรประจำตัวประชาชน (13 หลัก)','tel')+fld('username','ชื่อผู้ใช้')+fld('password','รหัสผ่าน','password'),async v=>{if(await api('reg_member',v)){X();TAB='';boot()}})}
function regC(){M('สมัครพนักงานขนส่ง',fld('first','ชื่อ')+fld('last','นามสกุล')+fld('phone','เบอร์ติดต่อ','tel')+fld('username','ชื่อผู้ใช้')+fld('password','รหัส','password')+fld('nid','เลขบัตรประชาชน (13 หลัก)','tel')+fld('addr','ที่อยู่')+fld('id_f','รูปบัตรประชาชนด้านหน้า (ถ่าย/เลือกจากคลังรูป)','ph')+fld('id_b','รูปบัตรประชาชนด้านหลัง','ph')+fld('birth','วันเกิด','birth'),async v=>{if(await api('reg_courier',v)){X();TAB='';boot();toast('ส่งคำขอแล้ว รอคลังอนุมัติ')}})}
function logM(){M('เข้าสู่ระบบ',fld('username','ชื่อผู้ใช้')+fld('password','รหัสผ่าน','password'),async v=>{if(await api('login',v)){X();TAB='';boot()}},'เข้าสู่ระบบ')}
async function out(){await api('logout');ME=null;TAB='';boot()}
V_.home=async()=>{const h=await api('home_get');return (h.media.map(m=>m.startsWith('data:video')?`<video src="${m}" controls style="width:100%"></video>`:`<img class=w style="width:100%" src="${m}" onclick=zoom(this.src)>`).join('')+h.items.map(i=>`<div class=card style="padding:12px"><b>${esc(i.title)}</b><p>${esc(i.detail)}</p></div>`).join(''))||'<p class=c>ยังไม่มีเนื้อหา</p>'};
V_.my=async()=>{const l=await api('p_list');return `<div class=card style="padding:12px" id=f>${fld('no','กรอกเลขพัสดุเพื่อติดตาม')}<button class=pr onclick="show(V().no)">ดูสถานะ</button></div>`+l.map(p=>`<div class=card><div class=h onclick="show('${p.no}')"><b>${p.no}</b><span>${ST[p.status]}</span></div></div>`).join('')};
async function show(no){const r=await api('track',{no});if(!r)return;DET=r;TAB='det';SUB='';await draw()}
V_.det=()=>{const p=DET.p,c=DET.c;const pts=[];p.ups.forEach(u=>u.loc.forEach(l=>pts.push(l)));AFTER=()=>map(pts,p.gps);
 return `<button onclick="TAB=ME.role=='member'?'my':ME.role=='courier'?'mine':ME.role=='wh'?'whp':'ad';draw()">← กลับ</button><div id=map></div><div class=card style="padding:12px"><b>${p.no}</b> — ${ST[p.status]}<br>ผู้ส่ง: ${esc(p.sname)} → ผู้รับ: ${esc(p.rname)}<br>${c?`พนักงานขนส่ง: ${esc(c.n)} โทร ${esc(c.ph)}`:'ยังไม่มีพนักงานรับงาน'}</div>`+p.ups.slice().reverse().map(u=>`<div class=st><small>${u.t}</small><br>${esc(u.x)}${u.loc.length?' 📍'+u.loc.map(l=>l[0]).join(', '):''}</div>`).join('')};
V_.send=()=>`<div class=card style="padding:12px" id=f>${fld('sname','ชื่อผู้ส่ง')+fld('saddr','ที่อยู่ผู้ส่ง')+fld('sphone','เบอร์ติดต่อผู้ส่ง','tel')+fld('sphoto','รูปที่ 1 รูปผู้ส่ง (ถ่ายภาพ)','cam')+fld('pphoto','รูปที่ 2 รูปพัสดุ (ถ่ายภาพ)','cam')+fld('rname','ชื่อผู้รับ')+fld('rphone','เบอร์ติดต่อผู้รับ','tel')+fld('raddr','ที่อยู่ผู้รับ')+fld('gps','พิกัด GPS ผู้รับ (ไม่บังคับ เช่น 13.75,100.50)')}<button class=pr onclick=doSend()>ตกลง</button></div>`;
async function doSend(){const r=await api('send',V());if(r){toast('เลขพัสดุของคุณ: '+r.no);alert('สร้างพัสดุสำเร็จ\nเลขพัสดุ: '+r.no);TAB='my';draw()}}
V_.nt=async()=>{const l=await api('nts');return l.length?l.map(n=>`<div class="card nt" style="padding:12px" onpointerdown="sx=event.clientX" onpointerup="if(event.clientX-sx>70)this.classList.add('sw')"><div><small>${n.t}</small><br>${esc(n.x)}</div><button class=del onclick="delN('${n.id}')">ลบ</button></div>`).join('')+'<p class=c>เลื่อนข้อความไปทางขวาเพื่อลบ</p>':'<p class=c>ไม่มีการแจ้งเตือน</p>'};
async function delN(id){if(cf('ลบการแจ้งเตือนนี้จริงหรือไม่?')){await api('dn',{id});draw()}}
V_.pf=()=>`<div class=card style="padding:16px;text-align:center"><div onclick=avM()>${ME.av?`<img src="${ME.av}" style="width:100px;height:100px;border-radius:50%;object-fit:cover">`:'<div class=big style="font-size:70px">👤</div>'}<br><small>กดที่รูปเพื่อเปลี่ยน</small></div><h3>${esc(ME.first)} ${esc(ME.last)}</h3><p>${rl(ME.role)} @${ME.username}</p>${ME.req?'<p>⏳ คำขอเป็นพนักงานรอการอนุมัติ</p>':''}<button class=pr onclick=pfM()>แก้ไขโปรไฟล์</button><button onclick=pwM()>เปลี่ยนรหัส</button><button class=dg onclick=out()>ออกจากระบบ</button></div>`;
function avM(){M('เปลี่ยนรูปโปรไฟล์',fld('av','เลือกรูปจากคลังรูปภาพ','ph'),async v=>{if(await api('set_av',v)){X();boot()}})}
function pfM(){M('แก้ไขโปรไฟล์ (ต้องรอแอดมินอนุมัติ)',fld('first','ชื่อ','text',[],ME.first)+fld('last','นามสกุล','text',[],ME.last)+fld('phone','เบอร์','tel',[],ME.phone)+fld('birth','วันเกิด (เช่น 12 ธันวาคม 2569)','text',[],ME.birth)+fld('nid','เลขบัตร ปชช. 13 หลัก','tel',[],ME.nid),async v=>{if(await api('edit_req',v)){X();toast('ส่งคำขอแก้ไขแล้ว รอแอดมินอนุมัติ')}})}
function pwM(){M('เปลี่ยนรหัสผ่าน',fld('old','รหัสปัจจุบัน','password')+fld('new','รหัสใหม่','password'),async v=>{if(await api('chpw',v)){X();toast('เปลี่ยนรหัสเรียบร้อย')}})}
V_.pw=()=>`<div class=card style="padding:16px;text-align:center"><p>บัญชี: ${esc(ME.username)} (${rl(ME.role)})</p><button class=pr onclick=pwM()>เปลี่ยนรหัส</button><button class=dg onclick=out()>ออกจากระบบ</button></div>`;
// ----- พนักงานขนส่ง -----
const ji=p=>`ผู้ส่ง: ${esc(p.sname)} ${esc(p.sphone)}<br>ที่อยู่ผู้ส่ง: ${esc(p.saddr)}<br>ผู้รับ: ${esc(p.rname)} ${esc(p.rphone)}<br>ที่อยู่ผู้รับ: ${esc(p.raddr)}<br>${p.weight?`น้ำหนัก ${p.weight} กก. ค่าขนส่ง ${p.fee} (${p.cod})`:''}`;
V_.jobs=async()=>{const l=await api('jobs');return l.length?l.map(p=>row(p.no+' <small>'+ST[p.status]+'</small>',ji(p)+`<p>เลื่อนเพื่อรับงาน →</p><input type=range min=0 max=100 value=0 onchange="if(this.value>92)acc('${p.no}');else this.value=0">`)).join(''):'<p class=c>ยังไม่มีงาน</p>'};
async function acc(no){if(await api('accept',{no})){toast('รับงานแล้ว');TAB='mine';draw()}}
V_.mine=async()=>{const l=await api('mine');return `<div class=card style="padding:12px" id=f>${fld('no','เปิดดูแผนที่/สถานะด้วยเลขพัสดุ')}<button onclick="show(V().no)">ดู</button></div>`+(l.length?l.map(p=>row(p.no+' <small>'+ST[p.status]+'</small>',ji(p),bt(`show('${p.no}')`,'แผนที่')+bt(`updM('${p.no}')`,'อัพเดทสถานะ','pr')+(p.status=='pick'?bt(`pkM('${p.no}')`,'รับพัสดุ','pr'):'')+(p.status=='got'?bt(`dwM('${p.no}')`,'ส่งพัสดุที่คลัง','pr'):'')+(p.status=='deliv'?bt(`dlM('${p.no}')`,'จัดส่งพัสดุ','pr'):''))).join(''):'<p class=c>ไม่มีงานที่รับไว้</p>')};
function updM(no){M('อัพเดทสถานะ',fld('text','ข้อความ เช่น กำลังนำส่ง ตอนนี้ถึงบางจากแล้ว'),async v=>{if(await api('upd',{no,text:v.text})){X();draw();toast('อัพเดทแล้ว')}})}
function pkM(no){M('บันทึกการรับพัสดุ',fld('weight','น้ำหนัก (กก.)','number')+fld('fee','ค่าขนส่ง (เงินในเกม)','number')+fld('cod','ช่องทางเก็บเงิน','sel',['ปลายทาง','จ่ายที่จุดรับ','ไม่มีเก็บเงินปลายทาง']),async v=>{if(await api('pickup',{...v,no})){X();draw()}})}
async function dwM(no){const w=await api('whs');M('ส่งพัสดุที่คลัง',fld('wh','ชื่อคลัง','sel',w)+fld('ph1','รูปที่ 1','cam')+fld('ph2','รูปที่ 2','cam')+fld('ph3','รูปที่ 3','cam'),async v=>{if(await api('drop_wh',{...v,no})){X();draw()}})}
function dlM(no){M('จัดส่งพัสดุ (ถ่าย 3 รูปหน้าบ้านลูกค้า)',fld('ph1','รูปที่ 1','cam')+fld('ph2','รูปที่ 2','cam')+fld('ph3','รูปที่ 3','cam'),async v=>{if(await api('deliver',{...v,no})){X();draw();toast('จัดส่งสำเร็จ')}})}
// ----- คลัง -----
V_.whp=async()=>{const l=await api('wh_list');return l.length?l.map(p=>row(p.no+' <small>'+ST[p.status]+'</small>',ji(p),p.status=='wh'?bt(`whs2('${p.no}')`,'นำขึ้นรถ','pr'):p.status=='van'?bt(`whs2('${p.no}')`,'ถึงปลายทาง เปิดให้พนักงานรับ','pr'):'')).join(''):'<p class=c>ไม่มีพัสดุในคลัง</p>'};
async function whs2(no){if(await api('wh_step',{no}))draw()}
V_.ap=async()=>{const l=await api('pend');return l.length?l.map(x=>row(esc(x.first+' '+x.last),`ผู้ใช้: ${esc(x.username)}<br>โทร: ${esc(x.phone)}<br>บัตร ปชช.: ${esc(x.nid)}<br>เกิด: ${esc(x.birth)}<br>ที่อยู่: ${esc(x.addr)}<br>${imgs([x.req.id_f,x.req.id_b])}`,bt(`cdo('${x.username}',1)`,'อนุมัติ','pr')+bt(`cdo('${x.username}',0)`,'ปฏิเสธ','dg'))).join(''):'<p class=c>ไม่มีคำขอ</p>'};
async function cdo(username,ok){if(await api('c_do',{username,ok})){toast('ดำเนินการแล้ว');draw()}}
// ----- แอดมิน -----
const SECT=[['regs','บันทึกการสมัครสมาชิก'],['done','บันทึกการจัดส่งสำเร็จ'],['eds','อนุมัติการแก้ไขข้อมูล'],['cap','อนุมัติพนักงานขนส่ง'],['hm','รูปภาพหน้าหลัก / ข้อความ'],['aw','เพิ่มคลังสินค้า'],['ap2','ตั้งค่าแอป (ชื่อ/โลโก้/โทนสี)'],['fk','ระบบกันที่อยู่ปลอม'],['trk','ค้นหาพัสดุ'],['lg','เช็คย้อนหลัง']];
V_.ad=async()=>{if(!SUB)return SECT.map(s=>`<div class=card><div class=h onclick="SUB='${s[0]}';draw()"><b>${s[1]}</b><span>›</span></div></div>`).join('');
 return `<button onclick="SUB='';draw()">← กลับ</button>`+await S_[SUB]()};
const S_={};
S_.regs=async()=>(await api('users')).map(x=>row(esc(x.first+' '+x.last)+' <small>'+rl(x.role)+'</small>',`ผู้ใช้: ${esc(x.username)}<br>โทร: ${esc(x.phone)}<br>เกิด: ${esc(x.birth||'')}<br>บัตร: ${esc(x.nid||'')}<br>สมัครเมื่อ: ${x.t||''}`,bt(`ue('${x.username}')`,'แก้ไข')+bt(`ud('${x.username}')`,'ลบ','dg'))).join('')||'<p class=c>ไม่มีข้อมูล</p>';
function ue(u){M('แก้ไขข้อมูล '+u,fld('f','ช่อง','sel',['first','last','phone'])+fld('v','ค่าใหม่'),async v=>{if(await api('u_edit',{username:u,...v})){X();draw()}})}
async function ud(u){if(cf()&&cf('ยืนยันอีกครั้ง: ลบผู้ใช้ '+u+' ?')){await api('u_del',{username:u});draw()}}
S_.done=async()=>(await api('done_list')).map(p=>row(p.no+' <small>'+esc(p.oname)+' → '+esc(p.rname)+'</small>',ji(p)+`<br>ลูกค้า: ${esc(p.oname)}<br>พนักงาน: ${esc(p.courier||'')}<br>เสร็จ: ${p.done}<br>รูปส่งสำเร็จ:<br>${imgs(p.dph)}<br>รูปที่คลัง:<br>${imgs(p.whp)}<hr>`+p.ups.map(u=>`<div class=st><small>${u.t}</small> ${esc(u.x)}</div>`).join(''),bt(`pe('${p.no}')`,'แก้ไข')+bt(`pd('${p.no}')`,'ลบ','dg'))).join('')||'<p class=c>ไม่มีข้อมูล</p>';
function pe(no){M('แก้ไขพัสดุ '+no,fld('f','ช่อง','sel',['sname','sphone','saddr','rname','rphone','raddr'])+fld('v','ค่าใหม่'),async v=>{if(await api('p_edit',{no,...v})){X();draw()}})}
async function pd(no){if(cf()){await api('p_del',{no});draw()}}
S_.eds=async()=>(await api('er_list')).map(e=>row(esc(e.username)+' <small>'+e.t+'</small>',`ชื่อ: ${esc(e.first)} ${esc(e.last)}<br>โทร: ${esc(e.phone)}<br>เกิด: ${esc(e.birth)}<br>บัตร: ${esc(e.nid)}`,bt(`erd('${e.username}',1)`,'ตกลง','pr')+bt(`erd('${e.username}',0)`,'ปฏิเสธ','dg'))).join('')||'<p class=c>ไม่มีคำขอ</p>';
async function erd(username,ok){if(await api('er_do',{username,ok})){toast('แจ้งเตือนผู้ใช้แล้ว');draw()}}
S_.cap=()=>V_.ap();
S_.hm=async()=>{const h=await api('home_get');return `<div class=card style="padding:12px" id=f><b>รูปภาพหน้าหลัก</b>${fld('media','เลือกรูปหรือวีดีโอจากคลัง','ph')}<button class=pr onclick=hmAdd()>ตกลง</button>${h.media.map((m,i)=>`<div>${m.startsWith('data:video')?'🎞 วีดีโอ':`<img class=t src="${m}">`} ${bt(`hmDel(${i})`,'ลบ','dg')}</div>`).join('')}</div><div class=card style="padding:12px"><button class=pr onclick=hiM()>＋ เพิ่มข้อความ</button>${h.items.map(i=>row(esc(i.title),esc(i.detail),bt(`hiDel('${i.id}')`,'ลบ','dg'))).join('')}</div>`};
async function hmAdd(){const v=V();if(!v.media){toast('เลือกไฟล์ก่อน');return}if(await api('home_media',v))draw()}
async function hmDel(i){if(cf()){await api('home_mdel',{i});draw()}}
function hiM(){M('เพิ่มข้อความหน้าหลัก',fld('title','หัวข้อ')+fld('detail','รายละเอียด','ta'),async v=>{if(await api('home_add',v)){X();draw()}})}
async function hiDel(id){if(cf()){await api('home_del',{id});draw()}}
S_.aw=()=>`<div class=card style="padding:12px" id=f>${fld('username','ชื่อผู้ใช้คลัง')+fld('password','รหัสคลัง','password')}<button class=pr onclick="addW()">ตกลง (เพิ่มได้สูงสุด 6 คลัง)</button></div>`;
async function addW(){if(await api('add_wh',V())){toast('เพิ่มคลังสำเร็จ');draw()}}
S_.ap2=()=>`<div class=card style="padding:12px" id=f>${fld('name','ชื่อแอป','text',[],CFG.name)+fld('logo','โปรไฟล์/โลโก้แอป (เลือกจากคลังรูป)','ph')+fld('theme','โทนสี (ต้องใส่รหัสแอดมินซ้ำ)','sel',['yo','bl','ro','rw'])}<small>yo=เหลืองส้ม bl=น้ำเงินฟ้า ro=แดงส้ม rw=แดงขาว</small>${fld('apw','รหัสแอดมิน (ใส่เมื่อเปลี่ยนโทนสี)','password')}<button class=pr onclick=saveC()>ตกลง</button></div>`;
async function saveC(){const v=V();if(v.theme==CFG.theme)delete v.theme;if(await api('set_cfg',v)){toast('บันทึกแล้ว');boot()}}
S_.fk=async()=>`<div class=card style="padding:12px" id=f>${fld('url','ลิงก์ไฟล์ฐานข้อมูลจาก GitHub (รูปแบบ [ที่อยู่ปลอม],)')}<button class=pr onclick=fkU()>นำเข้าจากลิงก์</button>${fld('text','หรือพิมพ์เอง (บรรทัดละ 1 รายการ หรือ [ที่อยู่],)','ta')}<button class=pr onclick=fkT()>เพิ่ม</button></div>`+(await api('fake_list')).map(f=>row(esc(f.x.slice(0,40)),esc(f.x),bt(`fkD('${f.id}')`,'ลบ','dg'))).join('');
async function fkU(){const r=await api('fake_add',{url:V().url});if(r){toast('เพิ่ม '+r.n+' รายการ');draw()}}
async function fkT(){const r=await api('fake_add',{text:V().text});if(r){toast('เพิ่ม '+r.n+' รายการ');draw()}}
async function fkD(id){if(cf()){await api('fake_del',{id});draw()}}
S_.trk=()=>V_.mine().then(()=>`<div class=card style="padding:12px" id=f>${fld('no','เลขพัสดุ')}<button class=pr onclick="show(V().no)">ดู</button></div>`);
S_.lg=async()=>(await api('logs')).map(l=>`<div class=st><small>${l.t}</small> <b>${esc(l.w)}</b>: ${esc(l.x)}</div>`).join('')||'<p class=c>ไม่มีประวัติ</p>';
boot();
</script></body></html>'''

if __name__ == "__main__":
    print("เปิดที่ http://localhost:%d  | แอดมิน: %s / %s" % (PORT, ADMIN_USER, ADMIN_PASSWORD))
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=PORT, threads=32)
    except ImportError:
        app.run(host="0.0.0.0", port=PORT, threaded=True)
