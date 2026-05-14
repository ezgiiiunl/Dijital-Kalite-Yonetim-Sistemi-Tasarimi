from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import pyodbc
from datetime import datetime, date
from flask import flash
import json

app = Flask(__name__)
app.secret_key = "key"


def get_db_connection():
    conn_str = (
        r"DRIVER={server};"
        r"SERVER=sql;"
        r"DATABASE=data;"
        r"Trusted_Connection=yes;"
        r"Encrypt=no;"
    )
    conn = pyodbc.connect(conn_str)
    return conn


# --- YARDIMCI FONKSİYONLAR ---

def satiri_dict_yap(cursor, satir):
    """
    pyodbc Row nesnesini → dict'e çevirir.
    jsonify() dict alır, Row nesnesi almaz. Bu yüzden gerekli.
    cursor.description → [(kolon_adi, tip...), ...] listesi verir.
    zip() ile kolon adı ve değeri eşleştirilir.
    """
    kolonlar = [kolon[0] for kolon in cursor.description]
    return dict(zip(kolonlar, satir))


def tarih_donustur(obj):
    """
    Python date/datetime nesneleri JSON'a otomatik dönüşmez.
    json.dumps(..., default=tarih_donustur) şeklinde kullanılır.
    "2025-01-08" gibi ISO formatında string'e çevirir.
    """
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Serileştirilemiyor: {type(obj)}")


# ---------------- GİRİŞ / ÇIKIŞ İŞLEMLERİ ----------------
@app.route('/')
def giriş_ekrani():
    if 'rol' in session:
        return redirect(url_for('panel'))
    return render_template("login.html")


@app.route('/login', methods=['POST'])
def login():
    rol = request.form.get('rol')
    if rol == 'editor':
        kullanici = request.form.get('kullanici')
        sifre = request.form.get('sifre')
        if kullanici == 'admin' and sifre == '1234':
            session['rol'] = 'editor'
            return redirect(url_for('panel'))
        else:
            return "Hatalı Şifre! <a href='/'>Geri Dön</a>"
    else:
        session['rol'] = 'izleyici'
        return redirect(url_for('panel'))


@app.route('/cikis')
def cikis():
    session.pop('rol', None)
    return redirect(url_for('giriş_ekrani'))


# ---------------- PANELLER ----------------
@app.route('/panel')
def panel():
    if 'rol' not in session:
        return redirect(url_for('giriş_ekrani'))
    return render_template("panel.html")




def _surec_to_dict(row):
    """pyodbc Row → sözlük"""
    return {
        "meta": {
            "kimlik": row.SurecKimlik,
            "ad": row.SurecAdi,
            "mudürlük": row.Mudürlük or "",
            "aciklama": row.Aciklama or "",
            "girdiler": row.Girdiler or "",
            "ciktilar": row.Ciktilar or "",
            "iliskili": row.IliskiliSurecler or "",
            "versiyon": row.Versiyon or "1.0",
            "durum": row.Durum or "Taslak",
        }
    }


# ─────────────────────────────────────────────
# SAYFA: /surec
# ─────────────────────────────────────────────
@app.route('/surec')
def surec():
    if 'rol' not in session:
        return redirect(url_for('giris_ekrani'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            sk.SurecKimlik,
            sk.SurecAdi,
            sk.Mudürlük,
            sk.Aciklama,
            sk.Girdiler,
            sk.Ciktilar,
            sk.IliskiliSurecler,
            sk.Versiyon,
            sk.Durum,
            sk.GuncellemeTarihi,
            COUNT(DISTINCT se.ElemanID) AS ElemanSayisi,
            COUNT(DISTINCT sb.BaglantiID) AS BaglantiSayisi
        FROM SurecKutuphanesi sk
        LEFT JOIN SurecEleman se ON se.SurecKimlik = sk.SurecKimlik
        LEFT JOIN SurecBaglanti sb ON sb.SurecKimlik = sk.SurecKimlik
        GROUP BY 
            sk.SurecKimlik,
            sk.SurecAdi,
            sk.Mudürlük,
            sk.Aciklama,
            sk.Girdiler,
            sk.Ciktilar,
            sk.IliskiliSurecler,
            sk.Versiyon,
            sk.Durum,
            sk.GuncellemeTarihi
        ORDER BY sk.GuncellemeTarihi DESC
    """)

    rows = cursor.fetchall()

    surecler = []
    for row in rows:
        d = _surec_to_dict(row)
        d["eleman_sayisi"] = row.ElemanSayisi
        d["baglanti_sayisi"] = row.BaglantiSayisi
        surecler.append(d)

    conn.close()
    return render_template('surec.html', surecler=surecler)


# ─────────────────────────────────────────────
# API: LİSTE
# ─────────────────────────────────────────────
@app.route('/surec/api/liste', methods=['GET'])
def surec_api_liste():
    if 'rol' not in session:
        return jsonify({'hata': 'Yetkisiz'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            sk.SurecID,
            sk.SurecKimlik,
            sk.SurecAdi,
            sk.Mudürlük,
            sk.Aciklama,
            sk.Girdiler,
            sk.Ciktilar,
            sk.IliskiliSurecler,
            sk.Versiyon,
            sk.Durum,
            sk.OlusturanKullanici,
            sk.OlusturmaTarihi,
            sk.GuncellemeTarihi,
            COUNT(DISTINCT se.ElemanID) AS ElemanSayisi,
            COUNT(DISTINCT sb.BaglantiID) AS BaglantiSayisi
        FROM SurecKutuphanesi sk
        LEFT JOIN SurecEleman se ON se.SurecKimlik = sk.SurecKimlik
        LEFT JOIN SurecBaglanti sb ON sb.SurecKimlik = sk.SurecKimlik
        GROUP BY 
            sk.SurecID,
            sk.SurecKimlik,
            sk.SurecAdi,
            sk.Mudürlük,
            sk.Aciklama,
            sk.Girdiler,
            sk.Ciktilar,
            sk.IliskiliSurecler,
            sk.Versiyon,
            sk.Durum,
            sk.OlusturanKullanici,
            sk.OlusturmaTarihi,
            sk.GuncellemeTarihi
        ORDER BY sk.GuncellemeTarihi DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    sonuc = []
    for row in rows:
        d = _surec_to_dict(row)
        d["elemanlar"] = []
        d["baglantilar"] = []
        d["eleman_sayisi"] = row.ElemanSayisi
        d["baglanti_sayisi"] = row.BaglantiSayisi
        sonuc.append(d)

    return jsonify(sonuc)


# ─────────────────────────────────────────────
# DETAY API
# ─────────────────────────────────────────────
@app.route('/surec/api/detay/<kimlik>', methods=['GET'])
def surec_api_detay(kimlik):
    if 'rol' not in session:
        return jsonify({'hata': 'Yetkisiz'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM SurecKutuphanesi WHERE SurecKimlik = ?
    """, kimlik)

    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'hata': 'Bulunamadı'}), 404

    veri = _surec_to_dict(row)

    cursor.execute("""
        SELECT * FROM SurecEleman WHERE SurecKimlik = ?
    """, kimlik)

    veri["elemanlar"] = [
        {
            "id": e.ElemanUID,
            "tip": e.Tip,
            "x": e.PosX,
            "y": e.PosY,
            "w": e.Genislik,
            "h": e.Yukseklik,
            "etiket": e.Etiket or "",
            "aciklama": e.Aciklama or "",
            "numa": e.NumaKodu or "",
            "renk": e.Renk,
        }
        for e in cursor.fetchall()
    ]

    cursor.execute("""
        SELECT * FROM SurecBaglanti WHERE SurecKimlik = ?
    """, kimlik)

    veri["baglantilar"] = [
        {
            "id": b.BaglantiUID,
            "kaynak": b.KaynakUID,
            "hedef": b.HedefUID,
            "tip": b.Tip,
            "etiket": b.Etiket or "",
        }
        for b in cursor.fetchall()
    ]

    conn.close()
    return jsonify(veri)


# ─────────────────────────────────────────────
# KAYDET
# ─────────────────────────────────────────────
@app.route('/surec/api/kaydet', methods=['POST'])
def surec_api_kaydet():
    if 'rol' not in session:
        return jsonify({'hata': 'Yetkisiz'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Yetki yok'}), 403

    veri = request.get_json(force=True)
    meta = veri.get('meta', {})
    elemanlar = veri.get('elemanlar', [])
    baglantilar = veri.get('baglantilar', [])

    kimlik = meta.get('kimlik')
    if not kimlik:
        return jsonify({'hata': 'Eksik kimlik'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(1) FROM SurecKutuphanesi WHERE SurecKimlik = ?
    """, kimlik)

    mevcut = cursor.fetchone()[0]

    if mevcut:
        cursor.execute("""
            UPDATE SurecKutuphanesi SET
                SurecAdi=?,
                Mudürlük=?,
                Aciklama=?,
                Girdiler=?,
                Ciktilar=?,
                IliskiliSurecler=?,
                Versiyon=?,
                Durum=?,
                GuncellemeTarihi=GETDATE()
            WHERE SurecKimlik=?
        """, (
            meta.get('ad'),
            meta.get('mudürlük'),
            meta.get('aciklama'),
            meta.get('girdiler'),
            meta.get('ciktilar'),
            meta.get('iliskili'),
            meta.get('versiyon'),
            meta.get('durum'),
            kimlik
        ))
    else:
        cursor.execute("""
            INSERT INTO SurecKutuphanesi
            (SurecKimlik, SurecAdi, Mudürlük, Aciklama,
             Girdiler, Ciktilar, IliskiliSurecler,
             Versiyon, Durum, OlusturanKullanici)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            kimlik,
            meta.get('ad'),
            meta.get('mudürlük'),
            meta.get('aciklama'),
            meta.get('girdiler'),
            meta.get('ciktilar'),
            meta.get('iliskili'),
            meta.get('versiyon'),
            meta.get('durum'),
            session.get('kullanici')
        ))

    conn.commit()
    conn.close()

    return jsonify({'durum': 'ok', 'kimlik': kimlik})


# ─────────────────────────────────────────────
# SİL
# ─────────────────────────────────────────────
@app.route('/surec/api/sil/<kimlik>', methods=['DELETE'])
def surec_api_sil(kimlik):
    if 'rol' not in session:
        return jsonify({'hata': 'Yetkisiz'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Yetki yok'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM SurecKutuphanesi WHERE SurecKimlik=?
    """, kimlik)

    conn.commit()
    conn.close()

    return jsonify({'durum': 'ok'})

# ---------------- DÖKÜMANTASYON ANA SAYFA ----------------
@app.route('/dokumantasyon')
def dokumantasyon():
    if 'rol' not in session:
        return redirect(url_for('giris_ekrani'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Dış Kaynaklı
    cursor.execute("""
        SELECT No, DokumanNo, DokumanAdi, DokumanTuru, RevizyonNo,
               YayinTarihi, DokumanSahibiBirim, Durum, Icerik
        FROM DisDokumanlar
        ORDER BY No DESC
    """)
    dis_veriler = cursor.fetchall()

    # 2. İç Kaynaklı
    cursor.execute("""
        SELECT No, DokumanNo, DokumanAdi, DokumanTuru, RevizyonNo,
               YayinTarihi, DokumanSahibiBirim, Durum, Icerik
        FROM IcDokumanlar
        ORDER BY No DESC
    """)
    ic_veriler = cursor.fetchall()

    # 3. Takip Listesi: Dış + İç kaynaklı birleşimi (otomatik)
    cursor.execute("""
        SELECT
            No, DokumanNo, DokumanAdi, DokumanTuru, RevizyonNo,
            YayinTarihi, DokumanSahibiBirim, Durum,
            N'Dış Kaynaklı' AS Kaynak
        FROM DisDokumanlar
        UNION ALL
        SELECT
            No, DokumanNo, DokumanAdi, DokumanTuru, RevizyonNo,
            YayinTarihi, DokumanSahibiBirim, Durum,
            N'İç Kaynaklı' AS Kaynak
        FROM IcDokumanlar
        ORDER BY DokumanNo
    """)
    takip_cols = [c[0] for c in cursor.description]
    takip_veriler = [dict(zip(takip_cols, row)) for row in cursor.fetchall()]

    conn.close()

    return render_template(
        'dokumantasyon.html',
        dis_veriler=dis_veriler,
        takip_veriler=takip_veriler,
        ic_veriler=ic_veriler,
    )


# ──────────────────────────────────────────────────────────────────────────────
# DIŞ KAYNAKLI CRUD
# ──────────────────────────────────────────────────────────────────────────────
@app.route('/dis_ekle', methods=['POST'])
def dis_ekle():
    if 'rol' not in session or session['rol'] != 'editor':
        return redirect(url_for('giris_ekrani'))

    f = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO DisDokumanlar
            (DokumanNo, DokumanAdi, DokumanTuru, RevizyonNo,
             YayinTarihi, DokumanSahibiBirim,Durum, Icerik)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f.get('DokumanNo'),
        f.get('DokumanAdi'),
        f.get('DokumanTuru'),
        f.get('RevizyonNo'),
        f.get('YayinTarihi'),
        f.get('DokumanSahibiBirim'),
        f.get('Durum', 'Aktif'),
        f.get('Icerik'),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for('dokumantasyon'))


@app.route('/dis_guncelle/<int:no>', methods=['POST'])
def dis_guncelle(no):
    if 'rol' not in session or session['rol'] != 'editor':
        return redirect(url_for('giris_ekrani'))

    f = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE DisDokumanlar SET
            DokumanNo          = ?,
            DokumanAdi         = ?,
            DokumanTuru        = ?,
            RevizyonNo         = ?,
            YayinTarihi        = ?,
            DokumanSahibiBirim = ?,

            Durum              = ?,
            Icerik             = ?
        WHERE No = ?
    """, (
        f.get('DokumanNo'),
        f.get('DokumanAdi'),
        f.get('DokumanTuru'),
        f.get('RevizyonNo'),
        f.get('YayinTarihi'),
        f.get('DokumanSahibiBirim'),

        f.get('Durum', 'Aktif'),
        f.get('Icerik'),
        no,
    ))
    conn.commit()
    conn.close()
    return redirect(url_for('dokumantasyon'))


@app.route('/dis_sil/<int:no>', methods=['POST'])
def dis_sil(no):
    if 'rol' not in session or session['rol'] != 'editor':
        return redirect(url_for('giris_ekrani'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM DisDokumanlar WHERE No = ?", (no,))
    conn.commit()
    conn.close()
    return redirect(url_for('dokumantasyon'))


# ──────────────────────────────────────────────────────────────────────────────
# İÇ KAYNAKLI CRUD
# ──────────────────────────────────────────────────────────────────────────────
@app.route('/ic_ekle', methods=['POST'])
def ic_ekle():
    if 'rol' not in session or session['rol'] != 'editor':
        return redirect(url_for('giris_ekrani'))

    f = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO IcDokumanlar
            (DokumanNo, DokumanAdi, DokumanTuru, RevizyonNo,
             YayinTarihi, DokumanSahibiBirim, Durum, Icerik)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f.get('DokumanNo'),
        f.get('DokumanAdi'),
        f.get('DokumanTuru'),
        f.get('RevizyonNo'),
        f.get('YayinTarihi'),
        f.get('DokumanSahibiBirim'),
        f.get('Durum', 'Aktif'),
        f.get('Icerik'),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for('dokumantasyon'))


@app.route('/ic_guncelle/<int:no>', methods=['POST'])
def ic_guncelle(no):
    if 'rol' not in session or session['rol'] != 'editor':
        return redirect(url_for('giris_ekrani'))

    f = request.form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE IcDokumanlar SET
            DokumanNo          = ?,
            DokumanAdi         = ?,
            DokumanTuru        = ?,
            RevizyonNo         = ?,
            YayinTarihi        = ?,
            DokumanSahibiBirim = ?,
            Durum              = ?,
            Icerik             = ?
        WHERE No = ?
    """, (
        f.get('DokumanNo'),
        f.get('DokumanAdi'),
        f.get('DokumanTuru'),
        f.get('RevizyonNo'),
        f.get('YayinTarihi'),
        f.get('DokumanSahibiBirim'),
        f.get('Durum', 'Aktif'),
        f.get('Icerik'),
        no,
    ))
    conn.commit()
    conn.close()
    return redirect(url_for('dokumantasyon'))


@app.route('/ic_sil/<int:no>', methods=['POST'])
def ic_sil(no):
    if 'rol' not in session or session['rol'] != 'editor':
        return redirect(url_for('giris_ekrani'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM IcDokumanlar WHERE No = ?", (no,))
    conn.commit()
    conn.close()
    return redirect(url_for('dokumantasyon'))


# ──────────────────────────────────────────────────────────────────────────────
# PROSEDÜR API (JSON kayıt)
# ──────────────────────────────────────────────────────────────────────────────
@app.route('/api/prosedur_kaydet', methods=['POST'])
def prosedur_kaydet():
    if 'rol' not in session or session['rol'] != 'editor':
        return jsonify({'error': 'Yetkisiz erişim'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geçersiz veri'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Aynı kod varsa güncelle, yoksa ekle
    cursor.execute("SELECT No FROM Prosedurler WHERE ProKod = ?", (data.get('kod'),))
    existing = cursor.fetchone()

    pro_json = json.dumps(data, ensure_ascii=False)

    if existing:
        cursor.execute("""
            UPDATE Prosedurler SET
                ProBaslik        = ?,
                ProRevizyon      = ?,
                ProTarih         = ?,
                ProDurum         = ?,
                ProSorumlu       = ?,
                ProAciklama      = ?,
                ProDataJson      = ?,
                GuncellemeTarihi = ?
            WHERE ProKod = ?
        """, (
            data.get('baslik'),
            data.get('revizyon'),
            data.get('tarih'),
            data.get('durum'),
            data.get('sorumlu'),
            data.get('aciklama'),
            pro_json,
            datetime.now(),
            data.get('kod'),
        ))
    else:
        cursor.execute("""
            INSERT INTO Prosedurler
                (ProKod, ProBaslik, ProRevizyon, ProTarih, ProDurum,
                 ProSorumlu, ProAciklama, ProDataJson)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('kod'),
            data.get('baslik'),
            data.get('revizyon'),
            data.get('tarih'),
            data.get('durum'),
            data.get('sorumlu'),
            data.get('aciklama'),
            pro_json,
        ))

    conn.commit()
    conn.close()
    return jsonify({'message': 'Prosedür kaydedildi ✓'})


# ================================================================
# UYGUNSUZLUK MODÜLÜ
# ================================================================

def risk_skorundan_tip_belirle(risk_skoru):
    """
    1  - 4  → 'Gözlem'
    5  - 9  → 'Minör'
    10 - 25 → 'Majör'
    None    → None
    """
    if risk_skoru is None:
        return None
    try:
        skor = int(risk_skoru)
    except (ValueError, TypeError):
        return None

    if skor <= 0:
        return None
    elif skor <= 4:
        return 'Gözlem'
    elif skor <= 9:
        return 'Minör'
    else:
        return 'Majör'


# =============================================================================
# SAYFA ROUTE — Uygunsuzluk sayfasını render et
# =============================================================================
@app.route('/uygunsuzluk')
def uygunsuzluk():
    if 'rol' not in session:
        return redirect(url_for('giriş_ekrani'))
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
            SELECT
                id,
                tanim,
                kaynak_turu,
                uygunsuzluk_tipi,
                ilgili_surec,
                mudurluk,
                CONVERT(NVARCHAR(10), tespit_tarihi, 23) AS tespit_tarihi,
                tespit_yeri,
                sorumlu,
                olasilik,
                etki,
                risk_skoru,
                durum,
                CONVERT(NVARCHAR(16), kayit_tarihi, 120) AS kayit_tarihi
            FROM uygunsuzluklar
            ORDER BY id DESC
        """)

    kolonlar = [col[0] for col in cursor.description]
    satirlar = cursor.fetchall()

    uygunsuzluklar = [dict(zip(kolonlar, satir)) for satir in satirlar]

    conn.close()

    return render_template('uygunsuzluk.html',uygunsuzluklar=uygunsuzluklar)


# =============================================================================
# API ROUTE 1 — Tüm Kayıtları Listele
# GET /uygunsuzluk/listele
# uygunsuzluk.html → tabloYenile() bu route'u çağırır.
# =============================================================================
@app.route('/uygunsuzluk/listele', methods=['GET'])
def uygunsuzluk_listele():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id,
                tanim,
                kaynak_turu,
                uygunsuzluk_tipi,
                ilgili_surec,
                mudurluk,
                CONVERT(NVARCHAR(10), tespit_tarihi, 23) AS tespit_tarihi,
                tespit_yeri,
                sorumlu,
                olasilik,
                etki,
                risk_skoru,
                durum,
                CONVERT(NVARCHAR(16), kayit_tarihi, 120) AS kayit_tarihi
            FROM uygunsuzluklar
            ORDER BY id DESC
        """)
        kolonlar = [col[0] for col in cursor.description]
        satirlar = cursor.fetchall()
        conn.close()

        sonuc = [dict(zip(kolonlar, satir)) for satir in satirlar]
        return jsonify(sonuc)

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# =============================================================================
# API ROUTE 2 — Tek Kayıt Getir
# GET /uygunsuzluk/<id>
# duzenleAc() ve problemDetayGoster() bu route'u çağırır.
# =============================================================================
@app.route('/uygunsuzluk/<int:kayit_id>', methods=['GET'])
def uygunsuzluk_getir(kayit_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id,
                tanim,
                kaynak_turu,
                uygunsuzluk_tipi,
                ilgili_surec,
                mudurluk,
                CONVERT(NVARCHAR(10), tespit_tarihi, 23) AS tespit_tarihi,
                tespit_yeri,
                sorumlu,
                olasilik,
                etki,
                risk_skoru,
                durum
            FROM uygunsuzluklar
            WHERE id = ?
        """, kayit_id)

        kolonlar = [col[0] for col in cursor.description]
        satir = cursor.fetchone()
        conn.close()

        if not satir:
            return jsonify({'hata': 'Kayıt bulunamadı'}), 404

        return jsonify(dict(zip(kolonlar, satir)))

    except Exception as e:
        return jsonify({'hata': str(e)}), 500



@app.route('/uygunsuzluk/ekle', methods=['POST'])
def uygunsuzluk_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli'}), 401

    try:
        veri = request.get_json()
        if not veri:
            return jsonify({'hata': 'Veri alınamadı'}), 400

        # Verileri modal'dan alıyoruz
        tanim = (veri.get('tanim') or veri.get('aciklama') or '').strip()
        mudurluk = (veri.get('mudurluk') or '').strip()
        tespit_tarihi = (veri.get('tespit_tarihi') or '').strip()
        sorumlu = (veri.get('sorumlu') or '').strip()
        kaynak_turu = (veri.get('kaynak_turu') or 'İç Denetim').strip()
        uygunsuzluk_tipi = (veri.get('uygunsuzluk_tipi') or 'Minör').strip()
        ilgili_surec = (veri.get('ilgili_surec') or '').strip()
        tespit_yeri = (veri.get('tespit_yeri') or '').strip()

        # Sayısal alanları güvenli şekilde alalım (Hata veren yer burasıydı)
        def guvenli_int(deger):
            try:
                return int(deger) if deger is not None and str(deger).strip() != "" else None
            except:
                return None

        olasilik_int = guvenli_int(veri.get('olasilik'))
        etki_int = guvenli_int(veri.get('etki'))
        risk_skoru = (olasilik_int * etki_int) if (olasilik_int and etki_int) else None

        # VERİTABANI BAĞLANTISI
        conn = get_db_connection()
        cursor = conn.cursor()

        # Senin attığın fotoğraftaki sütun sırasına göre yazıyorum
        cursor.execute("""
            INSERT INTO uygunsuzluklar (
                tanim, kaynak_turu, uygunsuzluk_tipi, ilgili_surec,
                mudurluk, tespit_tarihi, tespit_yeri, sorumlu,
                olasilik, etki, risk_skoru, durum, kayit_tarihi
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            tanim, kaynak_turu, uygunsuzluk_tipi, ilgili_surec,
            mudurluk, tespit_tarihi, tespit_yeri, sorumlu,
            olasilik_int, etki_int, risk_skoru, 'Açık'
        ))

        conn.commit()

        # ID'yi alırken None hatası almamak için en sağlam yol:
        cursor.execute("SELECT ISNULL(MAX(id), 0) FROM uygunsuzluklar")
        yeni_id = cursor.fetchone()[0]

        conn.close()
        return jsonify({'basarili': True, 'id': int(yeni_id)})

    except Exception as e:
        print(f"SİSTEM HATASI: {str(e)}")
        return jsonify({'hata': str(e)}), 500



# =============================================================================
# API ROUTE 4 — Kayıt Güncelle
# PUT /uygunsuzluk/guncelle/<id>
#
# Güncellenebilen alanlar:
#   tanim, ilgili_surec, mudurluk, tespit_tarihi,
#   tespit_yeri, sorumlu, olasilik, etki
#
# Korunan alanlar (değiştirilemez):
#   kaynak_turu     → kaydın kaynağı değiştirilemez
#   uygunsuzluk_tipi → Manuel kayıtlarda risk değişince otomatik güncellenir
#                      Denetim kayıtlarında hiç dokunulmaz
#   durum           → Sadece DF modülü (durum-guncelle route'u) değiştirir
# ============================================================================
@app.route('/uygunsuzluk/guncelle/<int:kayit_id>', methods=['PUT'])
def uygunsuzluk_guncelle(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403

    try:
        veri = request.get_json()
        if not veri:
            return jsonify({'hata': 'Geçersiz veri formatı'}), 400

        # ── Zorunlu Alan Kontrolü ──────────────────────────────────────
        tanim = (veri.get('tanim') or '').strip()
        mudurluk = (veri.get('mudurluk') or '').strip()
        tespit_tarihi = (veri.get('tespit_tarihi') or '').strip()
        sorumlu = (veri.get('sorumlu') or '').strip()

        if not tanim:
            return jsonify({'hata': 'Uygunsuzluk Tanımı boş olamaz'}), 400
        if not mudurluk:
            return jsonify({'hata': 'Müdürlük / Birim boş olamaz'}), 400
        if not tespit_tarihi:
            return jsonify({'hata': 'Tespit Tarihi boş olamaz'}), 400
        if not sorumlu:
            return jsonify({'hata': 'Sorumlu boş olamaz'}), 400

        # ── Risk Skoru: Sunucu tarafında yeniden hesapla ──────────────
        olasilik = veri.get('olasilik')
        etki = veri.get('etki')

        try:
            olasilik_int = int(olasilik) if olasilik else None
            etki_int = int(etki) if etki else None
        except (ValueError, TypeError):
            olasilik_int = None
            etki_int = None

        risk_skoru = (olasilik_int * etki_int) if (olasilik_int and etki_int) else None

        # ── Mevcut Kaydın kaynak_turu'nu Çek ──────────────────────────
        # Kaynak türüne göre tipi güncelleme kararı verilecek.
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT kaynak_turu FROM uygunsuzluklar WHERE id = ?",
            kayit_id
        )
        mevcut = cursor.fetchone()

        if not mevcut:
            conn.close()
            return jsonify({'hata': 'Kayıt bulunamadı'}), 404

        mevcut_kaynak = mevcut[0] or ''
        denetim_kaynaklari = ['İç Denetim', 'Dış Denetim']

        ilgili_surec = (veri.get('ilgili_surec') or '').strip() or None
        tespit_yeri = (veri.get('tespit_yeri') or '').strip() or None

        if mevcut_kaynak not in denetim_kaynaklari:
            # ── Manuel Kayıt: Tip de güncellenir ──────────────────────
            yeni_tip = risk_skorundan_tip_belirle(risk_skoru)
            cursor.execute("""
                UPDATE uygunsuzluklar SET
                    tanim            = ?,
                    ilgili_surec     = ?,
                    mudurluk         = ?,
                    tespit_tarihi    = ?,
                    tespit_yeri      = ?,
                    sorumlu          = ?,
                    olasilik         = ?,
                    etki             = ?,
                    risk_skoru       = ?,
                    uygunsuzluk_tipi = ?
                WHERE id = ?
            """,
                           tanim,
                           ilgili_surec,
                           mudurluk,
                           tespit_tarihi,
                           tespit_yeri,
                           sorumlu,
                           olasilik_int,
                           etki_int,
                           risk_skoru,
                           yeni_tip,
                           kayit_id
                           )
        else:
            # ── Denetim Kaynağı: Tip ve kaynak_turu korunur ───────────
            cursor.execute("""
                UPDATE uygunsuzluklar SET
                    tanim          = ?,
                    ilgili_surec   = ?,
                    mudurluk       = ?,
                    tespit_tarihi  = ?,
                    tespit_yeri    = ?,
                    sorumlu        = ?,
                    olasilik       = ?,
                    etki           = ?,
                    risk_skoru     = ?
                WHERE id = ?
            """,
                           tanim,
                           ilgili_surec,
                           mudurluk,
                           tespit_tarihi,
                           tespit_yeri,
                           sorumlu,
                           olasilik_int,
                           etki_int,
                           risk_skoru,
                           kayit_id
                           )

        conn.commit()
        conn.close()
        return jsonify({'basarili': True})

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# =============================================================================
# API ROUTE 5 — Kayıt Sil
# DELETE /uygunsuzluk/sil/<id>
# =============================================================================
@app.route('/uygunsuzluk/sil/<int:kayit_id>', methods=['DELETE'])
def uygunsuzluk_sil(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM uygunsuzluklar WHERE id = ?", kayit_id)
        conn.commit()
        conn.close()
        return jsonify({'basarili': True})

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# =============================================================================
# API ROUTE 6 — Durum Güncelle  ← SADECE DF MODÜLÜ ÇAĞIRIR
# PUT /uygunsuzluk/durum-guncelle/<id>
#
# Düzeltici Faaliyetler modülü uygunsuzluğun durumunu buradan değiştirir.
# uygunsuzluk.html bu route'u hiç çağırmaz.
#
# Kullanım (duzeltici_faaliyetler route'unuzdan):
#   DF kaydı açıldığında   → PUT /uygunsuzluk/durum-guncelle/<id>  {"durum": "Devam Ediyor"}
#   DF tamamlandığında     → PUT /uygunsuzluk/durum-guncelle/<id>  {"durum": "Kapatıldı"}
# =============================================================================
@app.route('/uygunsuzluk/durum-guncelle/<int:kayit_id>', methods=['PUT'])
def uygunsuzluk_durum_guncelle(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403

    try:
        veri = request.get_json()
        durum = (veri.get('durum') or '').strip()

        gecerli_durumlar = ['Açık', 'Devam Ediyor', 'Kapatıldı']
        if durum not in gecerli_durumlar:
            return jsonify({
                'hata': f'Geçersiz durum. Kabul edilenler: {gecerli_durumlar}'
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE uygunsuzluklar SET durum = ? WHERE id = ?",
            durum, kayit_id
        )
        conn.commit()
        conn.close()
        return jsonify({'basarili': True})

    except Exception as e:
        return jsonify({'hata': str(e)}), 500



def denetimden_uygunsuzluk_olustur(cursor, veri, uygunsuzluk_tipi):
    """
    Denetim kaynağından uygunsuzluk oluşturur.
    kaynak_turu ve uygunsuzluk_tipi dışarıdan verilir, risk hesaplanmaz.
    """
    cursor.execute("""
        INSERT INTO uygunsuzluklar (
            tanim,
            kaynak_turu,
            uygunsuzluk_tipi,
            ilgili_surec,
            mudurluk,
            tespit_tarihi,
            tespit_yeri,
            sorumlu,
            olasilik,
            etki,
            risk_skoru,
            durum
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
                   (veri.get('tanim') or '').strip(),
                   veri.get('kaynak_turu', 'İç Denetim'),
                   uygunsuzluk_tipi,
                   (veri.get('ilgili_surec') or '').strip() or None,
                   (veri.get('mudurluk') or '').strip(),
                   veri.get('tespit_tarihi'),
                   (veri.get('tespit_yeri') or '').strip() or None,
                   (veri.get('sorumlu') or '').strip(),
                   None,  # olasilik: denetimden gelenler için sonradan girilebilir
                   None,  # etki
                   None,  # risk_skoru
                   'Açık'  # durum her zaman Açık başlar
                   )


import os
import uuid
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'denetim')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpg', 'png'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def dosya_kaydet(file_obj, alt_klasor=''):
    if file_obj and allowed_file(file_obj.filename):
        ext = file_obj.filename.rsplit('.', 1)[1].lower()
        benzersiz = f"{uuid.uuid4().hex}.{ext}"
        klasor = os.path.join(UPLOAD_FOLDER, alt_klasor)
        os.makedirs(klasor, exist_ok=True)
        yol = os.path.join(klasor, benzersiz)
        file_obj.save(yol)
        return '/' + yol.replace('\\', '/')
    return None


# ── Ana Sayfa ──────────────────────────────────────────────────────────────
@app.route('/denetim')
def denetim_sayfasi():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, department, date, status, gecikme_neden FROM ic_denetim_program ORDER BY date")
    audits = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute("SELECT id, ad, birim, gorev_yeri, denetledigi_birim, sertifika, tarih FROM denetciler ORDER BY id")
    denetciler = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute("SELECT id, tip, iso, aciklama, sorumlu, kapanis, durum FROM ic_denetim_bulgular ORDER BY id")
    bulgular = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute("""
        SELECT t.id,
               CONCAT(a.department, ' – ', CONVERT(nvarchar, a.date, 104)) AS denetim,
               t.denetim_adi, t.toplanti_turu,
               CONVERT(nvarchar, t.toplanti_tarihi, 104) AS tarih,
               t.dosya_url
        FROM   tutanaklar t
        JOIN   ic_denetim_program a ON a.id = t.denetim_id
        ORDER  BY t.toplanti_tarihi DESC
    """)
    tutanaklar = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute("SELECT id, kurum, ad, uzmanlik, iletisim FROM dis_denetciler ORDER BY id")
    dis_denetciler = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute("SELECT id, tip, iso, aciklama, sorumlu, kapanis FROM dis_denetim_bulgular ORDER BY id")
    dis_bulgular = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute(
        "SELECT id, tur, ad, CONVERT(nvarchar, tarih, 104) AS tarih, yukleyen, url FROM dis_denetim_belgeler ORDER BY id")
    dis_belgeler = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    cur.execute("SELECT id, oneri_no, madde, aciklama, birim, aksiyon FROM dis_iyilestirmeler ORDER BY id")
    dis_iyilestirmeler = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    # ── Dış denetim programı (eksikti, eklendi) ──
    cur.execute("""
            SELECT id, kurum, tur,
                   CONVERT(nvarchar(10), tarih, 23) AS tarih,
                   standart, maddeler, durum
            FROM dis_denetim_program
            ORDER BY id
        """)
    dis_denetim_program = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    conn.close()
    return render_template(
        'denetim.html',
        audits=audits,
        denetciler=denetciler,
        bulgular=bulgular,
        tutanaklar=tutanaklar,
        dis_denetciler=dis_denetciler,
        dis_bulgular=dis_bulgular,
        dis_belgeler=dis_belgeler,
        dis_iyilestirmeler=dis_iyilestirmeler,
        dis_denetim_program=dis_denetim_program,  # ← eklendi
    )


# ══════════════════════════════════════════════════════════════════════════
#  İÇ DENETİM PROGRAMI
# ══════════════════════════════════════════════════════════════════════════

@app.route('/create_audit', methods=['POST'])
def create_audit():
    department = request.form.get('department', '').strip()
    date = request.form.get('date', '').strip()
    status = request.form.get('status', 'Planlandı')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ic_denetim_program (department, date, status) VALUES (?,?,?)",
        department, date, status
    )
    conn.commit()
    conn.close()
    flash('Denetim eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/update_audit_status/<int:audit_id>', methods=['POST'])
def update_audit_status(audit_id):
    data = request.get_json()
    status = data.get('status', '')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE ic_denetim_program SET status=? WHERE id=?", status, audit_id)
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/update_audit_gecikme/<int:audit_id>', methods=['POST'])
def update_audit_gecikme(audit_id):
    data = request.get_json()
    neden = data.get('gecikme_neden', '')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE ic_denetim_program SET gecikme_neden=? WHERE id=?", neden, audit_id)
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/update_audit/<int:audit_id>', methods=['POST'])
def update_audit(audit_id):
    data = request.get_json()
    department = data.get('department', '')
    date = data.get('date', '')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE ic_denetim_program SET department=?, date=? WHERE id=?",
        department, date, audit_id
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/delete_audit/<int:audit_id>', methods=['POST'])
def delete_audit(audit_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ic_denetim_program WHERE id=?", audit_id)
    conn.commit()
    conn.close()
    flash('Denetim silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DENETÇİLER
# ══════════════════════════════════════════════════════════════════════════

@app.route('/denetci_ekle', methods=['POST'])
def denetci_ekle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO denetciler (ad, birim, gorev_yeri, denetledigi_birim, sertifika, tarih) VALUES (?,?,?,?,?,?)",
        f.get('ad'), f.get('birim'), f.get('gorev_yeri'),
        f.get('denetledigi_birim'), f.get('sertifika'), f.get('tarih') or None
    )
    conn.commit()
    conn.close()
    flash('Denetçi eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/denetci_duzenle', methods=['POST'])
def denetci_duzenle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE denetciler SET ad=?, birim=?, gorev_yeri=?, denetledigi_birim=?, sertifika=?, tarih=? WHERE id=?",
        f.get('ad'), f.get('birim'), f.get('gorev_yeri'),
        f.get('denetledigi_birim'), f.get('sertifika'),
        f.get('tarih') or None, f.get('id')
    )
    conn.commit()
    conn.close()
    flash('Denetçi güncellendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/denetci_sil/<int:denetci_id>', methods=['POST'])
def denetci_sil(denetci_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM denetciler WHERE id=?", denetci_id)
    conn.commit()
    conn.close()
    flash('Denetçi silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  İÇ DENETİM BULGULARI
# ══════════════════════════════════════════════════════════════════════════

@app.route('/bulgu_ekle', methods=['POST'])
def bulgu_ekle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ic_denetim_bulgular (tip, iso, aciklama, sorumlu, kapanis, durum) VALUES (?,?,?,?,?,?)",
        f.get('tip'), f.get('iso'), f.get('aciklama'),
        f.get('sorumlu'), f.get('kapanis') or None, 'Açık'
    )
    conn.commit()
    conn.close()
    flash('Bulgu eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/bulgu_duzenle/<int:bulgu_id>', methods=['POST'])
def bulgu_duzenle(bulgu_id):
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE ic_denetim_bulgular SET tip=?, iso=?, aciklama=?, sorumlu=?, kapanis=? WHERE id=?",
        f.get('tip'), f.get('iso'), f.get('aciklama'),
        f.get('sorumlu'), f.get('kapanis') or None, bulgu_id
    )
    conn.commit()
    conn.close()
    flash('Bulgu güncellendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/bulgu_sil/<int:bulgu_id>', methods=['POST'])
def bulgu_sil(bulgu_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ic_denetim_bulgular WHERE id=?", bulgu_id)
    conn.commit()
    conn.close()
    flash('Bulgu silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  TUTANAKLAR
# ══════════════════════════════════════════════════════════════════════════

@app.route('/tutanak_yukle', methods=['POST'])
def tutanak_yukle():
    f = request.form
    file = request.files.get('tutanak_dosya')
    url = dosya_kaydet(file, 'tutanak') or ''
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tutanaklar (denetim_id, denetim_adi, toplanti_turu, toplanti_tarihi, dosya_url) VALUES (?,?,?,?,?)",
        f.get('denetim_id'), f.get('denetim_adi'),
        f.get('toplanti_turu'), f.get('toplanti_tarihi') or None, url
    )
    conn.commit()
    conn.close()
    flash('Tutanak yüklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/tutanak_sil/<int:tutanak_id>', methods=['POST'])
def tutanak_sil(tutanak_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tutanaklar WHERE id=?", tutanak_id)
    conn.commit()
    conn.close()
    flash('Tutanak silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DIŞ DENETÇİLER
# ══════════════════════════════════════════════════════════════════════════

@app.route('/dis_denetci_ekle', methods=['POST'])
def dis_denetci_ekle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dis_denetciler (kurum, ad, uzmanlik, iletisim) VALUES (?,?,?,?)",
        f.get('kurum'), f.get('ad'), f.get('uzmanlik'), f.get('iletisim')
    )
    conn.commit()
    conn.close()
    flash('Dış denetçi eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_denetci_duzenle', methods=['POST'])
def dis_denetci_duzenle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE dis_denetciler SET kurum=?, ad=?, uzmanlik=?, iletisim=? WHERE id=?",
        f.get('kurum'), f.get('ad'), f.get('uzmanlik'), f.get('iletisim'), f.get('id')
    )
    conn.commit()
    conn.close()
    flash('Dış denetçi güncellendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_denetci_sil/<int:denetci_id>', methods=['POST'])
def dis_denetci_sil(denetci_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dis_denetciler WHERE id=?", denetci_id)
    conn.commit()
    conn.close()
    flash('Dış denetçi silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DIŞ DENETİM BULGULARI
# ══════════════════════════════════════════════════════════════════════════

@app.route('/dis_bulgu_ekle', methods=['POST'])
def dis_bulgu_ekle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dis_denetim_bulgular (tip, iso, aciklama, sorumlu, kapanis) VALUES (?,?,?,?,?)",
        f.get('tip'), f.get('iso'), f.get('aciklama'),
        f.get('sorumlu'), f.get('kapanis') or None
    )
    conn.commit()
    conn.close()
    flash('Dış denetim bulgusu eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_bulgu_duzenle/<int:bulgu_id>', methods=['POST'])
def dis_bulgu_duzenle(bulgu_id):
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE dis_denetim_bulgular SET tip=?, iso=?, aciklama=?, sorumlu=?, kapanis=? WHERE id=?",
        f.get('tip'), f.get('iso'), f.get('aciklama'),
        f.get('sorumlu'), f.get('kapanis') or None, bulgu_id
    )
    conn.commit()
    conn.close()
    flash('Dış denetim bulgusu güncellendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_bulgu_sil/<int:bulgu_id>', methods=['POST'])
def dis_bulgu_sil(bulgu_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dis_denetim_bulgular WHERE id=?", bulgu_id)
    conn.commit()
    conn.close()
    flash('Dış denetim bulgusu silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DIŞ DENETİM BELGE HAVUZU
# ══════════════════════════════════════════════════════════════════════════

@app.route('/dis_belge_yukle', methods=['POST'])
def dis_belge_yukle():
    f = request.form
    file = request.files.get('belge_dosya')
    url = dosya_kaydet(file, 'dis_belge') or ''
    yukleyen = session.get('kullanici_adi', 'Sistem')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dis_denetim_belgeler (tur, ad, tarih, yukleyen, url) VALUES (?,?,?,?,?)",
        f.get('belge_turu'), f.get('belge_adi'),
        f.get('belge_tarihi') or None, yukleyen, url
    )
    conn.commit()
    conn.close()
    flash('Belge yüklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_belge_sil/<int:belge_id>', methods=['POST'])
def dis_belge_sil(belge_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dis_denetim_belgeler WHERE id=?", belge_id)
    conn.commit()
    conn.close()
    flash('Belge silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DIŞ DENETİM İYİLEŞTİRME ÖNERİLERİ (OFI)
# ══════════════════════════════════════════════════════════════════════════
@app.route('/dis_iyilestirme_ekle', methods=['POST'])
def dis_iyilestirme_ekle():
    # JSON (AJAX) veya form POST olarak çalışır
    if request.is_json:
        v = request.get_json()
        oneri_no = (v.get('oneri_no') or '').strip()
        madde = (v.get('madde') or '').strip()
        aciklama = (v.get('aciklama') or '').strip()
        birim = (v.get('birim') or '').strip()
        aksiyon = (v.get('aksiyon') or '').strip()
    else:
        f = request.form
        oneri_no = (f.get('oneri_no') or '').strip()
        madde = (f.get('madde') or '').strip()
        aciklama = (f.get('aciklama') or '').strip()
        birim = (f.get('birim') or '').strip()
        aksiyon = (f.get('aksiyon') or '').strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dis_iyilestirmeler (oneri_no, madde, aciklama, birim, aksiyon) VALUES (?,?,?,?,?)",
        oneri_no, madde, aciklama, birim, aksiyon
    )
    conn.commit()
    if request.is_json:
        cur.execute("SELECT SCOPE_IDENTITY()")
        yeni_id = int(cur.fetchone()[0])
        conn.close()
        return jsonify({
            'basarili': True,
            'id': yeni_id,
            'oneri_no': oneri_no,
            'madde': madde,
            'aciklama': aciklama,
            'birim': birim,
            'aksiyon': aksiyon
        })
    conn.close()
    flash('İyileştirme önerisi eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_iyilestirme_duzenle', methods=['POST'])
def dis_iyilestirme_duzenle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE dis_iyilestirmeler SET oneri_no=?, madde=?, aciklama=?, birim=?, aksiyon=? WHERE id=?",
        f.get('oneri_no'), f.get('madde'), f.get('aciklama'),
        f.get('birim'), f.get('aksiyon'), f.get('id')
    )
    conn.commit()
    conn.close()
    flash('İyileştirme önerisi güncellendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


@app.route('/dis_iyilestirme_sil/<int:ofi_id>', methods=['POST'])
def dis_iyilestirme_sil(ofi_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dis_iyilestirmeler WHERE id=?", ofi_id)
    conn.commit()
    conn.close()
    flash('İyileştirme önerisi silindi.', 'warning')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DÖF — Düzeltici Faaliyet
# ══════════════════════════════════════════════════════════════════════════

@app.route('/dof_ekle', methods=['POST'])
def dof_ekle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO dof_kayitlari
           (aciklama, kok_neden, sorumlu, hedef_tarih, oncelik, kaynak_id, durum, olusturma_tarihi)
           VALUES (?,?,?,?,?,?,?,GETDATE())""",
        f.get('aciklama'), f.get('kok_neden'), f.get('sorumlu'),
        f.get('hedef_tarih') or None, f.get('oncelik'),
        f.get('kaynak'), 'Açık'
    )
    conn.commit()
    conn.close()
    flash('DÖF kaydı oluşturuldu.', 'success')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  AKTARIM — Uygunsuzluk & İyileştirme
# ══════════════════════════════════════════════════════════════════════════




@app.route('/iyilestirme_aktar', methods=['POST'])
def iyilestirme_aktar():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO iyilestirme_kayitlari
           (oneri_no, ilgili_madde, aciklama, ilgili_birim, kaynak, durum, olusturma_tarihi)
           VALUES (?,?,?,?,?,?,GETDATE())""",
        f.get('oneri_no'), f.get('ilgili_madde'), f.get('aciklama'),
        f.get('ilgili_birim'), f.get('kaynak'), 'Değerlendirmede'
    )
    conn.commit()
    conn.close()
    flash('İyileştirme önerisi aktarıldı.', 'success')
    return redirect(url_for('denetim_sayfasi'))


# ══════════════════════════════════════════════════════════════════════════
#  DIŞ DENETİM PROGRAMI
# ══════════════════════════════════════════════════════════════════════════

@app.route('/dis_denetim_ekle', methods=['POST'])
def dis_denetim_ekle():
    f = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
            SELECT id, kurum, tur,
                   CONVERT(nvarchar(10), tarih, 23) AS tarih,
                   standart, maddeler, durum
            FROM dis_denetim_program
            ORDER BY id
        """)

    cur.execute("""
        INSERT INTO dis_denetim_program
        (kurum, tur, tarih, standart, maddeler, durum)
        VALUES (?,?,?,?,?,?)
    """,
        f.get('kurum'),
        f.get('tur'),
        f.get('tarih'),
        f.get('standart'),
        f.get('maddeler'),
        f.get('durum') or 'Planlandı'
    )
    conn.commit()
    conn.close()
    flash('Dış denetim eklendi.', 'success')
    return redirect(url_for('denetim_sayfasi'))


# ----------------------------------------------------------------
# DİĞER MODÜLLER
# ----------------------------------------------------------------
DIF_TABLO_MAP = {
    'gecici_onlem': 'dif_gecici_onlem',
    'kok_neden': 'dif_kok_neden',
    'kalici_cozum': 'dif_kalici_cozum',
    'tekrari_onle': 'dif_tekrari_onle',
}

DIF_KOLONLAR = {
    'gecici_onlem': [
        'id', 'uygunsuzluk_id', 'sorumlu', 'tarih', 'termin', 'risk',
        'aciklama', 'etki', 'kontrol', 'ek_bilgi', 'kpi', 'durum',
        'kayit_tarihi'
    ],
    'kok_neden': [
        'id', 'uygunsuzluk_id', 'sorumlu', 'tarih', 'aciklama',
        'ek_bilgi', 'risk', 'dogrulama', 'durum', 'kayit_tarihi'
    ],
    'kalici_cozum': [
        'id', 'uygunsuzluk_id', 'sorumlu', 'tarih', 'aciklama',
        'ek_bilgi', 'oncelik', 'ilerleme', 'kok_gereklilik', 'durum',
        'kayit_tarihi'
    ],
    'tekrari_onle': [
        'id', 'uygunsuzluk_id', 'sorumlu', 'tarih', 'aciklama',
        'ek_bilgi', 'risk', 'benzer_risk', 'dokuman', 'egitim',
        'etkinlik_skor', 'durum', 'kayit_tarihi'
    ],
}


# ============================================================
# DIF ANA SAYFA
# GET /dif
# ============================================================
@app.route('/dif')
def dif():
    if 'rol' not in session:
        return redirect(url_for('giriş_ekrani'))
    return render_template('dif.html')


# ============================================================
# DIF KAYIT EKLE
# POST /dif/ekle
# Body: { adim, uygunsuzluk_id, sorumlu, tarih, ... }
# adim: gecici | kokneden | kalici | tekrar
# ============================================================
@app.route('/dif/ekle', methods=['POST'])
def dif_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403

    try:
        veri = request.get_json()
        if not veri:
            return jsonify({'hata': 'Veri alınamadı'}), 400

        adim = (veri.get('adim') or '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Risk yoksa veya boşsa DÖF takibinden otomatik al
        def _risk_al(uyg_id, veri_risk):
            if veri_risk and str(veri_risk).strip():
                return str(veri_risk).strip()
            # DÖF takibinden al
            try:
                dof_no = uyg_id if str(uyg_id).startswith('DÖF') else f"DÖF-{uyg_id}"
                cursor.execute("SELECT risk FROM dif_takip WHERE uygunsuzluk_id = ?", dof_no)
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
            except Exception:
                pass
            return 'Düşük'

        if adim == 'gecici':
            uyg_id = veri.get('uygunsuzluk_id', '').strip()
            risk = _risk_al(uyg_id, veri.get('risk'))
            cursor.execute("""
                INSERT INTO dif_gecici_onlem
                    (uygunsuzluk_id, sorumlu, tarih, termin, risk,
                     aciklama, etki, kontrol, ek_bilgi, kpi, durum, kayit_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                uyg_id,
                veri.get('sorumlu', '').strip(),
                veri.get('tarih') or None,
                veri.get('termin') or None,
                risk,
                veri.get('aciklama', ''),
                veri.get('etki', ''),
                veri.get('kontrol', ''),
                veri.get('ek_bilgi', ''),
                veri.get('kpi', ''),
                veri.get('durum', 'Açık'),
            ))
            # Geçici önlem kaydedilince → takipte gecici_durum = 'Devam Ediyor'
            _dof_takip_adim_guncelle(cursor, uyg_id, 'gecici', 'Devam Ediyor')

        elif adim == 'kokneden':
            uyg_id = veri.get('uygunsuzluk_id', '').strip()
            risk = _risk_al(uyg_id, veri.get('risk'))
            cursor.execute("""
                INSERT INTO dif_kok_neden
                    (uygunsuzluk_id, sorumlu, tarih, aciklama,
                     ek_bilgi, risk, dogrulama, durum, kayit_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                uyg_id,
                veri.get('sorumlu', '').strip(),
                veri.get('tarih') or None,
                veri.get('aciklama', ''),
                veri.get('ek_bilgi', ''),
                risk,
                veri.get('dogrulama', 'Bekliyor'),
                veri.get('durum', 'Devam Ediyor'),
            ))
            # Kök neden kaydedilince → takipte kokneden_durum = 'Devam Ediyor'
            _dof_takip_adim_guncelle(cursor, uyg_id, 'kokneden', 'Devam Ediyor')

        elif adim == 'kalici':
            uyg_id = veri.get('uygunsuzluk_id', '').strip()
            cursor.execute("""
                INSERT INTO dif_kalici_cozum
                    (uygunsuzluk_id, sorumlu, tarih, aciklama,
                     ek_bilgi, oncelik, ilerleme, kok_gereklilik, durum, kayit_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                uyg_id,
                veri.get('sorumlu', '').strip(),
                veri.get('tarih') or None,
                veri.get('aciklama', ''),
                veri.get('ek_bilgi') or None,
                veri.get('oncelik', 'Düşük'),
                int(veri.get('ilerleme', 0) or 0),
                veri.get('kok_gereklilik', ''),
                veri.get('durum', 'Devam Ediyor'),
            ))
            # Kalıcı çözüm kaydedilince → takipte kalici_durum = 'Devam Ediyor'
            _dof_takip_adim_guncelle(cursor, uyg_id, 'kalici', 'Devam Ediyor')

        elif adim == 'tekrar':
            uyg_id = veri.get('uygunsuzluk_id', '').strip()
            risk = _risk_al(uyg_id, veri.get('risk'))
            cursor.execute("""
                INSERT INTO dif_tekrari_onle
                    (uygunsuzluk_id, sorumlu, tarih, aciklama, ek_bilgi,
                     risk, benzer_risk, dokuman, egitim, etkinlik_skor, durum, kayit_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                uyg_id,
                veri.get('sorumlu', '').strip(),
                veri.get('tarih') or None,
                veri.get('aciklama', ''),
                veri.get('ek_bilgi', ''),
                risk,
                veri.get('benzer_risk', ''),
                veri.get('dokuman', ''),
                veri.get('egitim', ''),
                int(veri.get('etkinlik_skor', 0) or 0),
                veri.get('durum', 'Kapatıldı'),
            ))
            # Tekrarı önle kaydedilince → DÖF tamamen kapatılır
            _dof_takip_otomatik_kapat(cursor, uyg_id)
            _uygunsuzluk_durum_guncelle_uyg_id(cursor, uyg_id, 'Kapatıldı')

        else:
            conn.close()
            return jsonify({'hata': f'Geçersiz adım: {adim}'}), 400

        conn.commit()
        conn.close()
        return jsonify({'basarili': True})

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DIF LİSTELE
# GET /dif/listele?adim=gecici_onlem|kok_neden|kalici_cozum|tekrari_onle
# ============================================================
@app.route('/dif/listele', methods=['GET'])
def dif_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli'}), 401

    adim = request.args.get('adim', '').strip()
    tablo = DIF_TABLO_MAP.get(adim)
    if not tablo:
        return jsonify({'hata': f'Geçersiz adım: {adim}'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM {tablo}
            ORDER BY id DESC
        """)
        kolonlar = [col[0] for col in cursor.description]
        satirlar = cursor.fetchall()
        conn.close()

        sonuc = []
        for satir in satirlar:
            d = dict(zip(kolonlar, satir))
            # date → string
            for k, v in d.items():
                if hasattr(v, 'strftime'):
                    d[k] = v.strftime('%Y-%m-%d')
            sonuc.append(d)

        return jsonify(sonuc)

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DIF GÜNCELLE (Adım kaydı)
# PUT /dif/guncelle/<id>
# Body: { adim, durum, ... }
# ============================================================
@app.route('/dif/guncelle/<int:kayit_id>', methods=['PUT'])
def dif_guncelle(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403
    try:
        veri = request.get_json()
        adim  = (veri.get('adim') or '').strip()
        # adim frontend'den 'gecici', 'kokneden', 'kalici', 'tekrar' olarak gelir
        adim_endpoint_map = {
            'gecici':   'gecici_onlem',
            'kokneden': 'kok_neden',
            'kalici':   'kalici_cozum',
            'tekrar':   'tekrari_onle',
        }
        endpoint = adim_endpoint_map.get(adim, adim)
        tablo = DIF_TABLO_MAP.get(endpoint)
        if not tablo:
            return jsonify({'hata': f'Geçersiz adım: {adim}'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Sadece durum güncellemesi (gerektiğinde genişletilebilir)
        durum = veri.get('durum')
        if durum:
            cursor.execute(f"UPDATE {tablo} SET durum = ? WHERE id = ?", durum, kayit_id)

        conn.commit()
        conn.close()
        return jsonify({'basarili': True})

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DIF SİL
# DELETE /dif/sil/<id>
# ============================================================
@app.route('/dif/sil/<int:kayit_id>', methods=['DELETE'])
def dif_sil(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403

    adim = request.args.get('adim', '').strip()
    # adim frontend'den 'gecici', 'kokneden', 'kalici', 'tekrar' olarak gelir
    adim_endpoint_map = {
        'gecici':   'gecici_onlem',
        'kokneden': 'kok_neden',
        'kalici':   'kalici_cozum',
        'tekrar':   'tekrari_onle',
    }
    endpoint = adim_endpoint_map.get(adim, adim)
    tablo = DIF_TABLO_MAP.get(endpoint)

    if not tablo:
        # adim yoksa tüm tablolarda arar
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            for t in DIF_TABLO_MAP.values():
                cursor.execute(f"DELETE FROM {t} WHERE id = ?", kayit_id)
            conn.commit()
            conn.close()
            return jsonify({'basarili': True})
        except Exception as e:
            return jsonify({'hata': str(e)}), 500

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {tablo} WHERE id = ?", kayit_id)
        conn.commit()
        conn.close()
        return jsonify({'basarili': True})
    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DÖF TAKİP LİSTELE
# GET /dif/takip/listele
# ============================================================
@app.route('/dif/takip/listele', methods=['GET'])
def dif_takip_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, uygunsuzluk_id, ozet, sorumlu,
                   CONVERT(NVARCHAR(10), hedef_tarih, 23) AS hedef_tarih,
                   gecici_durum, kokneden_durum, kalici_durum, tekrar_durum,
                   etkinlik, genel_durum, risk,
                   CONVERT(NVARCHAR(16), kayit_tarihi, 120) AS kayit_tarihi
            FROM dif_takip
            ORDER BY id DESC
        """)
        kolonlar = [col[0] for col in cursor.description]
        satirlar = cursor.fetchall()
        conn.close()
        return jsonify([dict(zip(kolonlar, s)) for s in satirlar])
    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DÖF TAKİP EKLE (Manuel)
# POST /dif/takip/ekle
# ============================================================
@app.route('/dif/takip/ekle', methods=['POST'])
def dif_takip_ekle():
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403
    try:
        veri = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dif_takip
                (uygunsuzluk_id, ozet, sorumlu, hedef_tarih,
                 gecici_durum, kokneden_durum, kalici_durum, tekrar_durum,
                 etkinlik, genel_durum, risk, kayit_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            veri.get('uygunsuzluk_id', '').strip(),
            veri.get('ozet', ''),
            veri.get('sorumlu', '').strip(),
            veri.get('hedef_tarih') or None,
            veri.get('gecici_durum', 'Bekliyor'),
            veri.get('kokneden_durum', 'Bekliyor'),
            veri.get('kalici_durum', 'Bekliyor'),
            veri.get('tekrar_durum', 'Bekliyor'),
            veri.get('etkinlik', ''),
            veri.get('genel_durum', 'Açık'),
            veri.get('risk', 'Düşük'),
        ))
        conn.commit()
        conn.close()
        return jsonify({'basarili': True})
    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DÖF TAKİP GÜNCELLE
# PUT /dif/takip/guncelle/<id>
# ============================================================
@app.route('/dif/takip/guncelle/<int:kayit_id>', methods=['PUT'])
def dif_takip_guncelle(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403
    try:
        veri = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dif_takip SET
                ozet           = ?,
                sorumlu        = ?,
                hedef_tarih    = ?,
                gecici_durum   = ?,
                kokneden_durum = ?,
                kalici_durum   = ?,
                tekrar_durum   = ?,
                etkinlik       = ?,
                genel_durum    = ?,
                risk           = ?
            WHERE id = ?
        """, (
            veri.get('ozet', ''),
            veri.get('sorumlu', '').strip(),
            veri.get('hedef_tarih') or None,
            veri.get('gecici_durum', 'Bekliyor'),
            veri.get('kokneden_durum', 'Bekliyor'),
            veri.get('kalici_durum', 'Bekliyor'),
            veri.get('tekrar_durum', 'Bekliyor'),
            veri.get('etkinlik', ''),
            veri.get('genel_durum', 'Açık'),
            veri.get('risk', 'Düşük'),
            kayit_id,
        ))
        conn.commit()
        conn.close()
        return jsonify({'basarili': True})
    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# DÖF TAKİP SİL
# DELETE /dif/takip/sil/<id>
# ============================================================
@app.route('/dif/takip/sil/<int:kayit_id>', methods=['DELETE'])
def dif_takip_sil(kayit_id):
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dif_takip WHERE id = ?", kayit_id)
        conn.commit()
        conn.close()
        return jsonify({'basarili': True})
    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# UYGUNSUZLUKTAN DIF'e AKTAR
# POST /dif/uygunsuzluktan-aktar
# Body: { uygunsuzluk_id: int }
# ============================================================
@app.route('/dif/uygunsuzluktan-aktar', methods=['POST'])
def dif_uygunsuzluktan_aktar():
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok'}), 403
    try:
        veri = request.get_json()
        uyg_db_id = veri.get('uygunsuzluk_id')
        if not uyg_db_id:
            return jsonify({'hata': 'Uygunsuzluk ID gerekli'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Uygunsuzluk verisini çek
        cursor.execute("""
            SELECT id, tanim, mudurluk, sorumlu, tespit_tarihi,
                   kaynak_turu, uygunsuzluk_tipi, risk_skoru, durum
            FROM uygunsuzluklar
            WHERE id = ?
        """, uyg_db_id)
        kolonlar = [col[0] for col in cursor.description]
        satir = cursor.fetchone()
        if not satir:
            conn.close()
            return jsonify({'hata': 'Uygunsuzluk bulunamadı'}), 404

        u = dict(zip(kolonlar, satir))

        # Zaten aktarılmış mı kontrol et
        dof_no = f"DÖF-{u['id']:04d}"
        cursor.execute("SELECT id FROM dif_takip WHERE uygunsuzluk_id = ?", dof_no)
        mevcut = cursor.fetchone()

        if mevcut:
            conn.close()
            return jsonify({'hata': 'Bu uygunsuzluk zaten DÖF takibine aktarılmış.', 'dof_no': dof_no}), 409

        # Risk seviyesini belirle
        risk_skoru = u.get('risk_skoru') or 0
        if risk_skoru >= 15:
            risk_seviye = 'Kritik'
        elif risk_skoru >= 10:
            risk_seviye = 'Yüksek'
        elif risk_skoru >= 5:
            risk_seviye = 'Orta'
        else:
            risk_seviye = 'Düşük'

        # DÖF takip kaydı oluştur
        cursor.execute("""
            INSERT INTO dif_takip
                (uygunsuzluk_id, ozet, sorumlu, hedef_tarih,
                 gecici_durum, kokneden_durum, kalici_durum, tekrar_durum,
                 etkinlik, genel_durum, risk, kayit_tarihi)
            VALUES (?, ?, ?, NULL, 'Bekliyor', 'Bekliyor', 'Bekliyor', 'Bekliyor',
                    '', 'Açık', ?, GETDATE())
        """, (
            dof_no,
            u.get('tanim', '')[:500],
            u.get('sorumlu', ''),
            risk_seviye,
        ))

        # Uygunsuzluk durumunu "Devam Ediyor" yap
        cursor.execute(
            "UPDATE uygunsuzluklar SET durum = 'Devam Ediyor' WHERE id = ?",
            uyg_db_id
        )

        conn.commit()
        conn.close()
        return jsonify({'basarili': True, 'dof_no': dof_no, 'uygunsuzluk': u})

    except Exception as e:
        return jsonify({'hata': str(e)}), 500


# ============================================================
# YARDIMCI FONKSİYONLAR (INTERNAL)
# ============================================================

def _dof_takip_adim_guncelle(cursor, uyg_id, adim, yeni_durum):
    """
    Belirli bir adım kaydedildiğinde DÖF takip panelinde o adımın durumunu günceller.
    adim: 'gecici' | 'kokneden' | 'kalici'
    Ayrıca genel_durum'u da 'Devam Ediyor' yapar (henüz kapanmadıysa).
    """
    try:
        dof_no = uyg_id if str(uyg_id).startswith('DÖF') else f"DÖF-{uyg_id}"
        kolon_map = {
            'gecici':   'gecici_durum',
            'kokneden': 'kokneden_durum',
            'kalici':   'kalici_durum',
        }
        kolon = kolon_map.get(adim)
        if not kolon:
            return
        # Takip kaydı varsa güncelle, genel_durum zaten Kapatıldı ise dokunma
        cursor.execute(f"""
            UPDATE dif_takip
            SET {kolon} = ?,
                genel_durum = CASE
                    WHEN genel_durum = 'Kapatıldı' THEN genel_durum
                    ELSE 'Devam Ediyor'
                END
            WHERE uygunsuzluk_id = ?
        """, yeni_durum, dof_no)
    except Exception:
        pass


def _dof_takip_otomatik_kapat(cursor, uyg_id):
    """
    Tekrarı önle kaydedilince tüm adımları ve genel_durum'u 'Kapatıldı' yapar.
    """
    try:
        dof_no = uyg_id if str(uyg_id).startswith('DÖF') else f"DÖF-{uyg_id}"
        cursor.execute("""
            UPDATE dif_takip SET
                tekrar_durum = 'Kapatıldı',
                genel_durum  = 'Kapatıldı'
            WHERE uygunsuzluk_id = ?
        """, dof_no)
    except Exception:
        pass


def _uygunsuzluk_durum_guncelle_uyg_id(cursor, uyg_id, yeni_durum):
    """
    uygunsuzluk_id (örn: DÖF-0042 veya sayı) ile uygunsuzluklar tablosunu günceller.
    DÖF-XXXX formatından sayıyı çıkararak UPDATE yapar.
    """
    try:
        if isinstance(uyg_id, int):
            db_id = uyg_id
        else:
            import re
            m = re.search(r'\d+', str(uyg_id))
            db_id = int(m.group()) if m else None
        if db_id:
            cursor.execute(
                "UPDATE uygunsuzluklar SET durum = ? WHERE id = ?",
                yeni_durum, db_id
            )
    except Exception:
        pass




@app.route('/ygg')
def ygg():
    if 'rol' not in session:
        return redirect(url_for('giris_ekrani'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # YGG Raporlar
    cursor.execute("SELECT * FROM YGG_RAPORLAR ORDER BY toplanti_tarihi DESC")
    kolonlar = [col[0] for col in cursor.description]
    raporlar = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]

    # YGG Kararlar
    cursor.execute("SELECT * FROM YGG_KARARLAR ORDER BY ygg_tarihi DESC")
    kolonlar = [col[0] for col in cursor.description]
    kararlar = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]

    # YGG Aksiyonlar
    cursor.execute("SELECT * FROM YGG_AKSIYONLAR ORDER BY baslangic DESC")
    kolonlar = [col[0] for col in cursor.description]
    aksiyonlar = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]

    conn.close()

    return render_template(
        'ygg.html',
        ygg_raporlar=raporlar,
        ygg_kararlar=kararlar,
        ygg_aksiyonlar=aksiyonlar
    )


# ============================================================
# 1. YGG RAPORLARI  (ISO 9.3.1)
# ============================================================

@app.route('/ygg/raporlar', methods=['GET'])
def ygg_raporlar_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    durum = request.args.get('durum', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if durum:
            cursor.execute(
                "SELECT * FROM YGG_RAPORLAR WHERE durum = ? ORDER BY toplanti_tarihi DESC",
                (durum,)
            )
        else:
            cursor.execute("SELECT * FROM YGG_RAPORLAR ORDER BY toplanti_tarihi DESC")
        kolonlar = [col[0] for col in cursor.description]
        data = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        return jsonify(data)
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/raporlar/<int:rapor_id>', methods=['GET'])
def ygg_rapor_getir(rapor_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM YGG_RAPORLAR WHERE id = ?", (rapor_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'hata': 'Kayıt bulunamadı.'}), 404
        kolonlar = [col[0] for col in cursor.description]
        return jsonify(dict(zip(kolonlar, row)))
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/raporlar/ekle', methods=['POST'])
def ygg_rapor_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    if not v.get('rapor_no') or not v.get('baskan'):
        return jsonify({'hata': 'Rapor No ve Başkanlık Eden zorunludur.'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO YGG_RAPORLAR
                (rapor_no, donem, toplanti_tarihi, toplanti_yeri,
                 baskan, kapsam, katilimci, durum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            v.get('rapor_no'),
            v.get('donem'),
            v.get('toplanti_tarihi') or None,
            v.get('toplanti_yeri'),
            v.get('baskan'),
            v.get('kapsam'),
            v.get('katilimci'),
            v.get('durum', 'Planlandı')
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Rapor eklendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/raporlar/guncelle/<int:rapor_id>', methods=['PUT'])
def ygg_rapor_guncelle(rapor_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE YGG_RAPORLAR SET
                rapor_no        = ?,
                donem           = ?,
                toplanti_tarihi = ?,
                toplanti_yeri   = ?,
                baskan          = ?,
                kapsam          = ?,
                katilimci       = ?,
                durum           = ?,
                guncelleme_tar  = GETDATE()
            WHERE id = ?
        """, (
            v.get('rapor_no'),
            v.get('donem'),
            v.get('toplanti_tarihi') or None,
            v.get('toplanti_yeri'),
            v.get('baskan'),
            v.get('kapsam'),
            v.get('katilimci'),
            v.get('durum', 'Planlandı'),
            rapor_id
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Rapor güncellendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/raporlar/sil/<int:rapor_id>', methods=['DELETE'])
def ygg_rapor_sil(rapor_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM YGG_RAPORLAR WHERE id = ?", (rapor_id,))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Rapor silindi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# 2. YGG KARARLAR  (ISO 9.3.3)
# ============================================================

@app.route('/ygg/kararlar', methods=['GET'])
def ygg_kararlar_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    durum = request.args.get('durum', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if durum:
            cursor.execute(
                "SELECT * FROM YGG_KARARLAR WHERE durum = ? ORDER BY ygg_tarihi DESC",
                (durum,)
            )
        else:
            cursor.execute("SELECT * FROM YGG_KARARLAR ORDER BY ygg_tarihi DESC")
        kolonlar = [col[0] for col in cursor.description]
        data = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        return jsonify(data)
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/kararlar/<int:karar_id>', methods=['GET'])
def ygg_karar_getir(karar_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM YGG_KARARLAR WHERE id = ?", (karar_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'hata': 'Kayıt bulunamadı.'}), 404
        kolonlar = [col[0] for col in cursor.description]
        return jsonify(dict(zip(kolonlar, row)))
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/kararlar/ekle', methods=['POST'])
def ygg_karar_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    if not v.get('karar_no') or not v.get('sorumlu') or not v.get('alinan_karar'):
        return jsonify({'hata': 'Karar No, Sorumlu ve Alınan Karar zorunludur.'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO YGG_KARARLAR
                (karar_no, ygg_tarihi, konu, alinan_karar,
                 sorumlu, hedef_tarih, durum, iso_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            v.get('karar_no'),
            v.get('ygg_tarihi') or None,
            v.get('konu'),
            v.get('alinan_karar'),
            v.get('sorumlu'),
            v.get('hedef_tarih') or None,
            v.get('durum', 'Planlandı'),
            v.get('iso_ref')
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Karar eklendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/kararlar/guncelle/<int:karar_id>', methods=['PUT'])
def ygg_karar_guncelle(karar_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE YGG_KARARLAR SET
                karar_no       = ?,
                ygg_tarihi     = ?,
                konu           = ?,
                alinan_karar   = ?,
                sorumlu        = ?,
                hedef_tarih    = ?,
                durum          = ?,
                iso_ref        = ?,
                guncelleme_tar = GETDATE()
            WHERE id = ?
        """, (
            v.get('karar_no'),
            v.get('ygg_tarihi') or None,
            v.get('konu'),
            v.get('alinan_karar'),
            v.get('sorumlu'),
            v.get('hedef_tarih') or None,
            v.get('durum', 'Planlandı'),
            v.get('iso_ref'),
            karar_id
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Karar güncellendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/kararlar/sil/<int:karar_id>', methods=['DELETE'])
def ygg_karar_sil(karar_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM YGG_KARARLAR WHERE id = ?", (karar_id,))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Karar silindi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# 3. YGG AKSİYONLAR  (ISO 10.1)
# ============================================================

@app.route('/ygg/aksiyonlar', methods=['GET'])
def ygg_aksiyonlar_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM YGG_AKSIYONLAR ORDER BY baslangic DESC")
        kolonlar = [col[0] for col in cursor.description]
        data = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        return jsonify(data)
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/aksiyonlar/<int:aksiyon_id>', methods=['GET'])
def ygg_aksiyon_getir(aksiyon_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM YGG_AKSIYONLAR WHERE id = ?", (aksiyon_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'hata': 'Kayıt bulunamadı.'}), 404
        kolonlar = [col[0] for col in cursor.description]
        return jsonify(dict(zip(kolonlar, row)))
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/aksiyonlar/ekle', methods=['POST'])
def ygg_aksiyon_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    if not v.get('aksiyon_no') or not v.get('sorumlu') or not v.get('aciklama'):
        return jsonify({'hata': 'Aksiyon No, Sorumlu ve Açıklama zorunludur.'}), 400
    try:
        ilerleme = int(v.get('ilerleme', 0))
        ilerleme = max(0, min(100, ilerleme))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO YGG_AKSIYONLAR
                (aksiyon_no, karar_no, aciklama, sorumlu,
                 baslangic, bitis, ilerleme, durum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            v.get('aksiyon_no'),
            v.get('karar_no'),
            v.get('aciklama'),
            v.get('sorumlu'),
            v.get('baslangic') or None,
            v.get('bitis') or None,
            ilerleme,
            v.get('durum', 'Planlandı')
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Aksiyon eklendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/aksiyonlar/guncelle/<int:aksiyon_id>', methods=['PUT'])
def ygg_aksiyon_guncelle(aksiyon_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    try:
        ilerleme = int(v.get('ilerleme', 0))
        ilerleme = max(0, min(100, ilerleme))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE YGG_AKSIYONLAR SET
                aksiyon_no     = ?,
                karar_no       = ?,
                aciklama       = ?,
                sorumlu        = ?,
                baslangic      = ?,
                bitis          = ?,
                ilerleme       = ?,
                durum          = ?,
                guncelleme_tar = GETDATE()
            WHERE id = ?
        """, (
            v.get('aksiyon_no'),
            v.get('karar_no'),
            v.get('aciklama'),
            v.get('sorumlu'),
            v.get('baslangic') or None,
            v.get('bitis') or None,
            ilerleme,
            v.get('durum', 'Planlandı'),
            aksiyon_id
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Aksiyon güncellendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/aksiyonlar/sil/<int:aksiyon_id>', methods=['DELETE'])
def ygg_aksiyon_sil(aksiyon_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM YGG_AKSIYONLAR WHERE id = ?", (aksiyon_id,))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Aksiyon silindi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# 4. YGG GİRDİLERİ  (ISO 9.3.2)
# ============================================================

@app.route('/ygg/girdiler', methods=['GET'])
def ygg_girdiler_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    rapor_no = request.args.get('rapor_no', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if rapor_no:
            cursor.execute(
                "SELECT * FROM YGG_GIRDILER WHERE rapor_no = ? ORDER BY tarih DESC",
                (rapor_no,)
            )
        else:
            cursor.execute("SELECT * FROM YGG_GIRDILER ORDER BY tarih DESC")
        kolonlar = [col[0] for col in cursor.description]
        data = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        return jsonify(data)
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/girdiler/<int:girdi_id>', methods=['GET'])
def ygg_girdi_getir(girdi_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM YGG_GIRDILER WHERE id = ?", (girdi_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'hata': 'Kayıt bulunamadı.'}), 404
        kolonlar = [col[0] for col in cursor.description]
        return jsonify(dict(zip(kolonlar, row)))
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/girdiler/ekle', methods=['POST'])
def ygg_girdi_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    if not v.get('rapor_no') or not v.get('sunan') or not v.get('ozet'):
        return jsonify({'hata': 'Rapor No, Sunan ve Özet zorunludur.'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO YGG_GIRDILER
                (rapor_no, konu, sunan, tarih, ozet)
            VALUES (?, ?, ?, ?, ?)
        """, (
            v.get('rapor_no'),
            v.get('konu', '9.3.2.a'),
            v.get('sunan'),
            v.get('tarih') or None,
            v.get('ozet')
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Girdi eklendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/girdiler/guncelle/<int:girdi_id>', methods=['PUT'])
def ygg_girdi_guncelle(girdi_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE YGG_GIRDILER SET
                rapor_no       = ?,
                konu           = ?,
                sunan          = ?,
                tarih          = ?,
                ozet           = ?,
                guncelleme_tar = GETDATE()
            WHERE id = ?
        """, (
            v.get('rapor_no'),
            v.get('konu'),
            v.get('sunan'),
            v.get('tarih') or None,
            v.get('ozet'),
            girdi_id
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Girdi güncellendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/girdiler/sil/<int:girdi_id>', methods=['DELETE'])
def ygg_girdi_sil(girdi_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM YGG_GIRDILER WHERE id = ?", (girdi_id,))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Girdi silindi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# 5. YGG ÇIKTILARI  (ISO 9.3.3)
# ============================================================

@app.route('/ygg/ciktilar', methods=['GET'])
def ygg_ciktilar_listele():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    rapor_no = request.args.get('rapor_no', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if rapor_no:
            cursor.execute(
                "SELECT * FROM YGG_CIKTILAR WHERE rapor_no = ? ORDER BY id DESC",
                (rapor_no,)
            )
        else:
            cursor.execute("SELECT * FROM YGG_CIKTILAR ORDER BY id DESC")
        kolonlar = [col[0] for col in cursor.description]
        data = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        return jsonify(data)
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/ciktilar/<int:cikti_id>', methods=['GET'])
def ygg_cikti_getir(cikti_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM YGG_CIKTILAR WHERE id = ?", (cikti_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'hata': 'Kayıt bulunamadı.'}), 404
        kolonlar = [col[0] for col in cursor.description]
        return jsonify(dict(zip(kolonlar, row)))
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/ciktilar/ekle', methods=['POST'])
def ygg_cikti_ekle():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    if not v.get('rapor_no') or not v.get('aciklama'):
        return jsonify({'hata': 'Rapor No ve Açıklama zorunludur.'}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO YGG_CIKTILAR
                (rapor_no, tur, karar_no, aciklama, durum)
            VALUES (?, ?, ?, ?, ?)
        """, (
            v.get('rapor_no'),
            v.get('tur', '9.3.3.a'),
            v.get('karar_no'),
            v.get('aciklama'),
            v.get('durum', 'Planlandı')
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Çıktı eklendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/ciktilar/guncelle/<int:cikti_id>', methods=['PUT'])
def ygg_cikti_guncelle(cikti_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    v = request.get_json()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE YGG_CIKTILAR SET
                rapor_no       = ?,
                tur            = ?,
                karar_no       = ?,
                aciklama       = ?,
                durum          = ?,
                guncelleme_tar = GETDATE()
            WHERE id = ?
        """, (
            v.get('rapor_no'),
            v.get('tur'),
            v.get('karar_no'),
            v.get('aciklama'),
            v.get('durum', 'Planlandı'),
            cikti_id
        ))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Çıktı güncellendi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


@app.route('/ygg/ciktilar/sil/<int:cikti_id>', methods=['DELETE'])
def ygg_cikti_sil(cikti_id):
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    if session.get('rol') != 'editor':
        return jsonify({'hata': 'Bu işlem için yetkiniz yok.'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM YGG_CIKTILAR WHERE id = ?", (cikti_id,))
        conn.commit()
        return jsonify({'durum': 'ok', 'mesaj': 'Çıktı silindi.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# 6. KPI ÖZET  —  GET /ygg/kpi
# ============================================================

@app.route('/ygg/kpi', methods=['GET'])
def ygg_kpi():
    if 'rol' not in session:
        return jsonify({'hata': 'Oturum gerekli.'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM YGG_RAPORLAR)                                AS toplam_ygg,
                (SELECT COUNT(*) FROM YGG_KARARLAR   WHERE durum = 'Tamamlandı')   AS tamam_karar,
                (SELECT COUNT(*) FROM YGG_AKSIYONLAR WHERE durum = 'Devam Ediyor') AS devam_aksiyon,
                (SELECT COUNT(*) FROM YGG_KARARLAR   WHERE durum = 'Gecikti')
              + (SELECT COUNT(*) FROM YGG_AKSIYONLAR WHERE durum = 'Gecikti')      AS gecikti
        """)
        row = cursor.fetchone()
        return jsonify({
            'toplam_ygg': row[0],
            'tamam_karar': row[1],
            'devam_aksiyon': row[2],
            'gecikti': row[3]
        })
    except Exception as e:
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


def satir_to_dict(cursor, satir):
    """pyodbc Row nesnesini dict'e çevirir."""
    if satir is None:
        return None
    kolonlar = [col[0] for col in cursor.description]
    return dict(zip(kolonlar, satir))


def satirlar_to_dict(cursor, satirlar):
    kolonlar = [col[0] for col in cursor.description]
    return [dict(zip(kolonlar, s)) for s in satirlar]


def oturum_kontrol():
    return 'rol' in session


def editor_kontrol():
    return session.get('rol') == 'editor'


# ════════════════════════════════════════════════════════════════════
#  GET /oneriler — Ana sayfa, liste
# ════════════════════════════════════════════════════════════════════
@app.route('/oneriler')
def oneriler():
    if not oturum_kontrol():
        return redirect(url_for('giris_ekrani'))

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                id, oneri_no, kaynak, denetim_adi, denetim_tarihi,
                ilgili_madde, aciklama, ilgili_birim, sorumlu,
                hedef_tarih, oncelik, durum, tamamlanma,
                etki, kolaylik, aksiyon,
                created_at, updated_at
            FROM iyilestirme_onerileri
            ORDER BY created_at DESC
        """)
        satirlar = satirlar_to_dict(cur, cur.fetchall())

        # Tarih alanlarını string'e çevir — Jinja2 için
        for o in satirlar:
            for alan in ('denetim_tarihi', 'hedef_tarih', 'created_at', 'updated_at'):
                if isinstance(o.get(alan), (date, datetime)):
                    o[alan] = o[alan].strftime('%Y-%m-%d')

    finally:
        conn.close()

    return render_template(
        'öneriler.html',
        iyilestirme_onerileri=satirlar
    )


# ════════════════════════════════════════════════════════════════════
#  POST /oneriler/ekle — Yeni öneri
# ════════════════════════════════════════════════════════════════════
@app.route('/oneriler/ekle', methods=['POST'])
def oneri_ekle():
    if not oturum_kontrol():
        return jsonify({'hata': 'Oturum açınız'}), 401
    if not editor_kontrol():
        return jsonify({'hata': 'Yetkiniz yok'}), 403

    veri = request.get_json()

    if not veri.get('oneri_no') or not veri.get('aciklama'):
        return jsonify({'hata': 'Öneri No ve Açıklama zorunludur'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Mükerrer oneri_no kontrolü
        cur.execute(
            "SELECT id FROM iyilestirme_onerileri WHERE oneri_no = ?",
            (veri['oneri_no'],)
        )
        if cur.fetchone():
            return jsonify({'hata': f"'{veri['oneri_no']}' numarası zaten kullanımda"}), 409

        cur.execute("""
            INSERT INTO iyilestirme_onerileri
                (oneri_no, kaynak, denetim_adi, denetim_tarihi,
                 ilgili_madde, aciklama, ilgili_birim, sorumlu,
                 hedef_tarih, oncelik, durum, tamamlanma,
                 etki, kolaylik, aksiyon, olusturan)
            OUTPUT INSERTED.id
            VALUES
                (?, ?, ?, ?,
                 ?, ?, ?, ?,
                 ?, ?, ?, ?,
                 ?, ?, ?, ?)
        """, (
            veri['oneri_no'],
            veri.get('kaynak', 'Manuel'),
            veri.get('denetim_adi') or None,
            veri.get('denetim_tarihi') or None,
            veri.get('ilgili_madde') or None,
            veri['aciklama'],
            veri.get('ilgili_birim') or None,
            veri.get('sorumlu') or None,
            veri.get('hedef_tarih') or None,
            veri.get('oncelik', 'Orta'),
            veri.get('durum', 'Değerlendirmede'),
            int(veri.get('tamamlanma', 0)),
            int(veri.get('etki', 2)),
            int(veri.get('kolaylik', 2)),
            veri.get('aksiyon') or None,
            session.get('kullanici_adi', 'sistem')
        ))

        yeni_id = cur.fetchone()[0]

        # Aksiyon notu varsa geçmişe yaz
        if veri.get('aksiyon'):
            cur.execute("""
                INSERT INTO ofi_aksiyonlar
                    (oneri_id, aksiyon_metni, yapan_kullanici,
                     tamamlanma_pct, durum_degisimi)
                VALUES (?, ?, ?, ?, ?)
            """, (
                yeni_id,
                veri['aksiyon'],
                session.get('kullanici_adi', 'sistem'),
                int(veri.get('tamamlanma', 0)),
                veri.get('durum', 'Değerlendirmede')
            ))

        conn.commit()
        return jsonify({'basarili': True, 'id': yeni_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════
#  POST /oneriler/<id>/guncelle — Öneri güncelle
# ════════════════════════════════════════════════════════════════════
@app.route('/oneriler/<int:oneri_id>/guncelle', methods=['POST'])
def oneri_guncelle(oneri_id):
    if not oturum_kontrol():
        return jsonify({'hata': 'Oturum açınız'}), 401
    if not editor_kontrol():
        return jsonify({'hata': 'Yetkiniz yok'}), 403

    veri = request.get_json()

    if not veri.get('oneri_no') or not veri.get('aciklama'):
        return jsonify({'hata': 'Öneri No ve Açıklama zorunludur'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Mevcut kaydı al — aksiyon geçmişi karşılaştırması için
        cur.execute(
            "SELECT durum, tamamlanma, aksiyon FROM iyilestirme_onerileri WHERE id = ?",
            (oneri_id,)
        )
        satir = cur.fetchone()
        if not satir:
            return jsonify({'hata': 'Öneri bulunamadı'}), 404

        mevcut_durum = satir[0]
        mevcut_tamamlanma = satir[1]
        mevcut_aksiyon = satir[2] or ''

        yeni_durum = veri.get('durum', 'Değerlendirmede')
        yeni_tamamlanma = int(veri.get('tamamlanma', 0))
        yeni_aksiyon = veri.get('aksiyon', '') or ''

        cur.execute("""
            UPDATE iyilestirme_onerileri SET
                oneri_no       = ?,
                kaynak         = ?,
                denetim_adi    = ?,
                denetim_tarihi = ?,
                ilgili_madde   = ?,
                aciklama       = ?,
                ilgili_birim   = ?,
                sorumlu        = ?,
                hedef_tarih    = ?,
                oncelik        = ?,
                durum          = ?,
                tamamlanma     = ?,
                etki           = ?,
                kolaylik       = ?,
                aksiyon        = ?,
                updated_at     = GETDATE()
            WHERE id = ?
        """, (
            veri['oneri_no'],
            veri.get('kaynak', 'Manuel'),
            veri.get('denetim_adi') or None,
            veri.get('denetim_tarihi') or None,
            veri.get('ilgili_madde') or None,
            veri['aciklama'],
            veri.get('ilgili_birim') or None,
            veri.get('sorumlu') or None,
            veri.get('hedef_tarih') or None,
            veri.get('oncelik', 'Orta'),
            yeni_durum,
            yeni_tamamlanma,
            int(veri.get('etki', 2)),
            int(veri.get('kolaylik', 2)),
            yeni_aksiyon or None,
            oneri_id
        ))

        # Durum veya tamamlanma değiştiyse geçmişe kaydet
        durum_degisti = mevcut_durum != yeni_durum
        tamamlanma_degisti = mevcut_tamamlanma != yeni_tamamlanma

        if (durum_degisti or tamamlanma_degisti) and yeni_aksiyon:
            cur.execute("""
                INSERT INTO ofi_aksiyonlar
                    (oneri_id, aksiyon_metni, yapan_kullanici,
                     tamamlanma_pct, durum_degisimi)
                VALUES (?, ?, ?, ?, ?)
            """, (
                oneri_id,
                yeni_aksiyon,
                session.get('kullanici_adi', 'sistem'),
                yeni_tamamlanma,
                yeni_durum if durum_degisti else None
            ))

        conn.commit()
        return jsonify({'basarili': True}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════
#  POST /oneriler/<id>/sil — Öneri sil
# ════════════════════════════════════════════════════════════════════
@app.route('/oneriler/<int:oneri_id>/sil', methods=['POST'])
def oneri_sil(oneri_id):
    if not oturum_kontrol():
        return jsonify({'hata': 'Oturum açınız'}), 401
    if not editor_kontrol():
        return jsonify({'hata': 'Yetkiniz yok'}), 403

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT id FROM iyilestirme_onerileri WHERE id = ?", (oneri_id,)
        )
        if not cur.fetchone():
            return jsonify({'hata': 'Öneri bulunamadı'}), 404

        # ON DELETE CASCADE tanımlı olduğu için alt tablolar otomatik silinir
        cur.execute(
            "DELETE FROM iyilestirme_onerileri WHERE id = ?", (oneri_id,)
        )

        conn.commit()
        return jsonify({'basarili': True}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'hata': str(e)}), 500
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════
#  GET /oneriler/<id>/detay — Tek öneri + aksiyon geçmişi (JSON)
# ════════════════════════════════════════════════════════════════════
@app.route('/oneriler/<int:oneri_id>/detay')
def oneri_detay(oneri_id):
    if not oturum_kontrol():
        return jsonify({'hata': 'Oturum açınız'}), 401

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM iyilestirme_onerileri WHERE id = ?", (oneri_id,)
        )
        oneri = satir_to_dict(cur, cur.fetchone())
        if not oneri:
            return jsonify({'hata': 'Bulunamadı'}), 404

        # Tarih serileştirme
        for alan in ('denetim_tarihi', 'hedef_tarih', 'created_at', 'updated_at'):
            if isinstance(oneri.get(alan), (date, datetime)):
                oneri[alan] = oneri[alan].strftime('%Y-%m-%d')

        # Aksiyon geçmişi
        cur.execute("""
            SELECT aksiyon_metni, yapan_kullanici,
                   aksiyon_tarihi, tamamlanma_pct, durum_degisimi
            FROM ofi_aksiyonlar
            WHERE oneri_id = ?
            ORDER BY aksiyon_tarihi DESC
        """, (oneri_id,))
        aksiyonlar = satirlar_to_dict(cur, cur.fetchall())
        for a in aksiyonlar:
            if isinstance(a.get('aksiyon_tarihi'), datetime):
                a['aksiyon_tarihi'] = a['aksiyon_tarihi'].strftime('%Y-%m-%d %H:%M')

        oneri['aksiyonlar'] = aksiyonlar
        return jsonify(oneri), 200

    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════
#  GET /oneriler/analiz — KPI + grafik verileri (JSON)
# ════════════════════════════════════════════════════════════════════
@app.route('/oneriler/analiz')
def oneri_analiz():
    if not oturum_kontrol():
        return jsonify({'hata': 'Oturum açınız'}), 401

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # KPI özeti
        cur.execute("""
            SELECT
                COUNT(*)                                                        AS toplam,
                SUM(CASE WHEN durum = 'Değerlendirmede' THEN 1 ELSE 0 END)     AS bekliyor,
                SUM(CASE WHEN durum = 'Uygulamada'      THEN 1 ELSE 0 END)     AS uygulamada,
                SUM(CASE WHEN durum = 'Tamamlandı'      THEN 1 ELSE 0 END)     AS tamamlandi,
                SUM(CASE WHEN durum = 'Gecikti'         THEN 1 ELSE 0 END)     AS gecikti,
                SUM(CASE WHEN durum NOT IN ('Tamamlandı','İptal')
                          AND hedef_tarih < CAST(GETDATE() AS DATE)
                     THEN 1 ELSE 0 END)                                        AS sure_gecen,
                ROUND(AVG(CAST(tamamlanma AS FLOAT)), 1)                       AS ort_tamamlanma
            FROM iyilestirme_onerileri
        """)
        kpi = satir_to_dict(cur, cur.fetchone())

        # Kaynak dağılımı
        cur.execute("""
            SELECT kaynak, COUNT(*) AS sayi
            FROM iyilestirme_onerileri
            GROUP BY kaynak
        """)
        kaynak_dagilim = satirlar_to_dict(cur, cur.fetchall())

        # Birim dağılımı (top 10)
        cur.execute("""
            SELECT TOP 10 ilgili_birim AS birim, COUNT(*) AS sayi
            FROM iyilestirme_onerileri
            WHERE ilgili_birim IS NOT NULL
            GROUP BY ilgili_birim
            ORDER BY sayi DESC
        """)
        birim_dagilim = satirlar_to_dict(cur, cur.fetchall())

        # ISO madde dağılımı
        cur.execute("""
            SELECT ilgili_madde AS madde, COUNT(*) AS sayi
            FROM iyilestirme_onerileri
            WHERE ilgili_madde IS NOT NULL
            GROUP BY ilgili_madde
            ORDER BY sayi DESC
        """)
        iso_dagilim = satirlar_to_dict(cur, cur.fetchall())

        # Aylık trend (bu yıl)
        cur.execute("""
            SELECT MONTH(denetim_tarihi) AS ay, COUNT(*) AS sayi
            FROM iyilestirme_onerileri
            WHERE YEAR(denetim_tarihi) = YEAR(GETDATE())
              AND denetim_tarihi IS NOT NULL
            GROUP BY MONTH(denetim_tarihi)
            ORDER BY ay
        """)
        aylik_trend = satirlar_to_dict(cur, cur.fetchall())

        return jsonify({
            'kpi': kpi,
            'kaynak_dagilim': kaynak_dagilim,
            'birim_dagilim': birim_dagilim,
            'iso_dagilim': iso_dagilim,
            'aylik_trend': aylik_trend
        }), 200

    finally:
        conn.close()


@app.route('/risk')
def risk():
    if 'rol' not in session: return redirect(url_for('giriş_ekrani'))
    return render_template("risk.html")
# =============================================================================
# DIŞ DENETİM PROGRAMI SİLME ROUTE'U
# =============================================================================
@app.route('/dis_denetim_sil/<int:program_id>', methods=['POST'])
def dis_denetim_sil(program_id):
    if 'rol' not in session or session.get('rol') != 'editor':
        flash('Bu işlem için yetkiniz yok.', 'danger')
        return redirect(url_for('denetim_sayfasi'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Veritabanındaki tablo adının 'dis_denetim_program' olduğundan emin ol
        cursor.execute("DELETE FROM dis_denetim_program WHERE id = ?", program_id)
        conn.commit()
        conn.close()
        flash('Dış denetim program kaydı başarıyla silindi.', 'warning')
    except Exception as e:
        flash(f'Silme işlemi sırasında hata oluştu: {str(e)}', 'danger')

    return redirect(url_for('denetim_sayfasi'))

if __name__ == '__main__':
    app.run(debug=True)
