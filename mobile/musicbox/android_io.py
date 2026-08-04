"""Pomocnicze IO dla Androida (content:// URI) i desktopu."""
import os

_ANDROID = bool(
    os.environ.get("ANDROID_ARGUMENT")
    or os.environ.get("ANDROID_APP_PATH")
    or os.environ.get("P4A_BOOTSTRAP")
)
if not _ANDROID:
    try:
        import android  # noqa: F401  (modul dostarczany przez python-for-android)
        _ANDROID = True
    except Exception:
        _ANDROID = False

_materialized = []

_debug = None


def set_debug_logger(fn):
    """Ustawia funkcje logowania (np. app._debug_log) dla zdarzen Android."""
    global _debug
    _debug = fn


def _dbg(msg):
    if _debug is not None:
        try:
            _debug(msg)
        except Exception:
            pass


def is_android():
    return _ANDROID


def status_bar_height():
    """Wysokosc status bara w dp (0 na desktopie)."""
    if not _ANDROID:
        return 0
    try:
        from jnius import autoclass

        Resources = autoclass("android.content.res.Resources")
        resources = Resources.getSystem()
        ident = resources.getIdentifier("status_bar_height", "dimen", "android")
        if ident <= 0:
            return 0
        px = resources.getDimensionPixelSize(ident)
        density = resources.getDisplayMetrics().density
        return round(px / density) if density else 0
    except Exception:
        return 0


def _activity():
    from jnius import autoclass

    python_activity = autoclass("org.kivy.android.PythonActivity")
    return python_activity.mActivity


def _resolve_media_documents(uri, resolver, DocumentsContract, autoclass):
    """Sciaga realna sciezke z doc id typu 'audio:<id>' dla media.documents.

    Dziala na API <29 (lub gdy _data jest widoczne). Zwraca sciezke lub None.
    """
    doc_id = DocumentsContract.getDocumentId(uri)
    if ":" not in doc_id:
        return None
    media_type, media_id = doc_id.split(":", 1)
    table = {
        "audio": "android.provider.MediaStore$Audio$Media",
        "video": "android.provider.MediaStore$Video$Media",
        "image": "android.provider.MediaStore$Images$Media",
    }.get(media_type)
    if not table:
        return None
    cls = autoclass(table)
    cursor = resolver.query(
        cls.EXTERNAL_CONTENT_URI, ["_data"], "_id=?", [media_id], None
    )
    if cursor is not None:
        try:
            if cursor.moveToFirst():
                idx = cursor.getColumnIndex("_data")
                if idx >= 0:
                    return cursor.getString(idx) or None
        finally:
            cursor.close()
    return None


def uri_to_path(uri):
    """Najlepszy wysilek: zamien content:// URI na realna sciezke (pusty jesli sie nie da)."""
    if not uri:
        return uri
    if not _ANDROID or not str(uri).startswith("content://"):
        return uri
    try:
        from jnius import autoclass

        Uri = autoclass("android.net.Uri")
        DocumentsContract = autoclass("android.provider.DocumentsContract")
        Environment = autoclass("android.os.Environment")
        resolver = _activity().getContentResolver()
        uri = Uri.parse(str(uri))

        authority = uri.getAuthority()
        _dbg("uri_to_path: authority=" + str(authority))
        if authority == "com.android.externalstorage.documents":
            doc_id = DocumentsContract.getDocumentId(uri)
            if ":" in doc_id:
                file_type, file_name = doc_id.split(":", 1)
                base = Environment.getExternalStorageDirectory().getAbsolutePath()
                return os.path.join(base, file_name)

        if authority == "com.android.providers.downloads.documents":
            doc_id = DocumentsContract.getDocumentId(uri)
            try:
                from jnius import cast
                ContentUris = autoclass("android.content.ContentUris")
                Long = autoclass("java.lang.Long")
                down = ContentUris.withAppendedId(
                    Uri.parse("content://downloads/public_downloads"),
                    Long.valueOf(doc_id),
                )
                cursor = resolver.query(down, ["_data"], None, None, None)
                if cursor is not None:
                    try:
                        if cursor.moveToFirst():
                            idx = cursor.getColumnIndex("_data")
                            if idx >= 0:
                                return cursor.getString(idx) or uri
                    finally:
                        cursor.close()
            except Exception:
                pass

        if authority == "com.android.providers.media.documents":
            path = _resolve_media_documents(uri, resolver, DocumentsContract, autoclass)
            if path:
                return path

        MediaStore = autoclass("android.provider.MediaStore$MediaColumns")
        cursor = resolver.query(uri, [MediaStore.DATA], None, None, None)
        if cursor is not None:
            try:
                if cursor.moveToFirst():
                    idx = cursor.getColumnIndex(MediaStore.DATA)
                    if idx >= 0:
                        return cursor.getString(idx) or uri
            finally:
                cursor.close()
    except Exception:
        pass
    return uri


def _read_stream_all(stream):
    """Odczytuje caly InputStream do bytes.

    Bajt-po-bajcie przez read() (jedyny 100% pewny sposob w jnius;
    InputStream nie ma read(int), a bytearray->byte[] bywa zawodny).
    """
    out = bytearray()
    try:
        while True:
            b = stream.read()
            if b is None:
                break
            b = int(b)
            if b < 0:
                break
            out.append(b)
        return bytes(out)
    except Exception:
        return b""


def read_bytes(uri):
    """Odczyt bajtow z content:// URI (Android) lub normalnej sciezki."""
    if not uri:
        return b""
    if _ANDROID and str(uri).startswith("content://"):
        try:
            from jnius import autoclass

            Uri = autoclass("android.net.Uri")
            resolver = _activity().getContentResolver()
            stream = resolver.openInputStream(Uri.parse(str(uri)))
            if stream is None:
                return b""
            try:
                return _read_stream_all(stream)
            finally:
                try:
                    stream.close()
                except Exception:
                    pass
        except Exception as e:
            _dbg("read_bytes: wyjatek " + repr(e))
            return b""
    try:
        with open(uri, "rb") as f:
            return f.read()
    except OSError:
        return b""


def _app_cache_dir():
    """Prywatny katalog cache aplikacji (zawsze zapisywalny) albo None."""
    if not _ANDROID:
        return None
    try:
        from jnius import autoclass

        cache = _activity().getCacheDir()
        if cache is not None:
            return cache.getAbsolutePath()
    except Exception:
        return None
    return None


def external_log_dir():
    """Widoczny katalog aplikacji na dysku wspoldzielonym (zawsze zapisywalny).

    Zwraca np. /storage/emulated/0/Android/data/<pkg>/files — widoczny w
    menedzerze plikow przy dostepie do wszystkich plikow.
    """
    if not _ANDROID:
        return None
    try:
        from jnius import autoclass

        files = _activity().getExternalFilesDir(None)
        if files is not None:
            return files.getAbsolutePath()
    except Exception:
        return None
    return None


def _uri_display_name(uri):
    """Probuje wyciagnac oryginalna nazwe pliku z content:// URI."""
    if not _ANDROID:
        return None
    try:
        from jnius import autoclass

        Uri = autoclass("android.net.Uri")
        DocumentsContract = autoclass("android.provider.DocumentsContract")
        resolver = _activity().getContentResolver()
        u = Uri.parse(str(uri))
        name = None
        try:
            doc = DocumentsContract.getDocumentId(u)
            if doc and ":" in doc:
                tail = doc.split(":", 1)[1]
                base = os.path.basename(tail.replace("/", os.sep))
                if base:
                    name = base
        except Exception:
            pass
        if not name:
            cursor = resolver.query(u, ["_display_name"], None, None, None)
            if cursor is not None:
                try:
                    if cursor.moveToFirst():
                        idx = cursor.getColumnIndex("_display_name")
                        if idx >= 0:
                            name = cursor.getString(idx) or None
                finally:
                    cursor.close()
        return name
    except Exception:
        return None


def musicbox_dir():
    """Zwraca (i tworzy) folder MusicBox/ na pamieci wspoldzielonej."""
    if not _ANDROID:
        return None
    try:
        from jnius import autoclass

        Environment = autoclass("android.os.Environment")
        base = Environment.getExternalStorageDirectory().getAbsolutePath()
        d = os.path.join(base, "MusicBox")
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        return d if os.path.isdir(d) else None
    except Exception as e:
        _dbg("musicbox_dir: wyjatek " + repr(e))
        return None


def persist_to_musicbox(data, name=None):
    """Kopiuje bajty .m3u do MusicBox/ i zwraca sciezke (lub None)."""
    mdir = musicbox_dir()
    if not mdir:
        return None
    if not name or "/" in name or "\\" in name or ".." in name:
        import uuid

        name = "musicbox_import_" + uuid.uuid4().hex + ".m3u"
    if not name.lower().endswith(".m3u"):
        name += ".m3u"
    target = os.path.join(mdir, name)
    try:
        with open(target, "wb") as f:
            f.write(data)
        return target
    except OSError:
        return None


def all_files_access():
    """Czy aplikacja ma 'Wszystkie pliki' (MANAGE_EXTERNAL_STORAGE, API 30+)."""
    if not _ANDROID:
        return True
    try:
        from jnius import autoclass

        Environment = autoclass("android.os.Environment")
        if android_api_level() >= 30:
            return bool(Environment.isExternalStorageManager())
        return True
    except Exception:
        return False


def open_all_files_settings():
    """Otwiera systemowy ekran 'Wszystkie pliki' dla tej aplikacji."""
    if not _ANDROID:
        return False
    try:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Settings = autoclass("android.provider.Settings")
        activity = _activity()
        uri = Uri.fromParts("package", activity.getPackageName(), None)
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, uri)
        activity.startActivity(intent)
        return True
    except Exception:
        return False


_PLAYBACK_SERVICE = "org.musicbox.musicbox.KeepAliveService"


def start_playback_service(title=None, cover=None, playing=True):
    """Uruchamia foreground service i aktualizuje powiadomienie (title/cover/playing)."""
    if not _ANDROID:
        return False
    try:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        activity = _activity()
        intent = Intent()
        intent.setClassName(activity.getPackageName(), _PLAYBACK_SERVICE)
        if title:
            intent.putExtra("title", title)
        if cover:
            intent.putExtra("cover", cover)
        intent.putExtra("playing", bool(playing))
        if android_api_level() >= 26:
            activity.startForegroundService(intent)
        else:
            activity.startService(intent)
        return True
    except Exception:
        return False


def set_playback_paused(paused):
    """Zmienia stan powiadomienia (pauza/wznowienie) bez zatrzymywania serwisu."""
    return start_playback_service(playing=not paused)


def stop_playback_service():
    """Zatrzymuje foreground service (pauza/stop/koniec odtwarzania)."""
    if not _ANDROID:
        return False
    try:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        activity = _activity()
        intent = Intent()
        intent.setClassName(activity.getPackageName(), _PLAYBACK_SERVICE)
        activity.stopService(intent)
        return True
    except Exception:
        return False


def resolve_playlist_path(uri):
    """Zwraca path, ktora nadaje sie do Playlist.load_m3u.

    Na desktopie to sam path. Na Androidzie materializuje content:// URI
    do widocznego folderu MusicBox/ (gdy jest pelny dostep) albo do
    prywatnego cache aplikacji (fallback, sprzatany).
    """
    if not uri:
        return None
    if _ANDROID and str(uri).startswith("content://"):
        real = uri_to_path(uri)
        _dbg("resolve: real=" + str(real))
        if real and os.path.isfile(real):
            if all_files_access():
                data = read_bytes(uri)
                _dbg("resolve: real-path read_bytes len=" + str(len(data)))
                if data:
                    persist_to_musicbox(data, _uri_display_name(uri))
            return real
        data = read_bytes(uri)
        _dbg("resolve: read_bytes len=" + str(len(data)))
        if not data:
            _dbg("resolve: puste dane, zwracam None")
            return None
        target = persist_to_musicbox(data, _uri_display_name(uri))
        _dbg("resolve: persist_to_musicbox=" + str(target))
        if target:
            return target
        cache = _app_cache_dir()
        _dbg("resolve: fallback cache=" + str(cache))
        if not cache:
            return None
        import uuid

        tmp = os.path.join(cache, "musicbox_import_" + uuid.uuid4().hex + ".m3u")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
        except OSError:
            return None
        _materialized.append(tmp)
        return tmp
    return uri if os.path.isfile(uri) else None


def is_materialized_import(path):
    """Czy path to materializacja content:// do pliku tymczasowego."""
    return path in _materialized


def cleanup_import_files():
    """Usuwa tymczasowe pliki materializowanych importow .m3u."""
    while _materialized:
        tmp = _materialized.pop()
        try:
            os.remove(tmp)
        except OSError:
            pass


def android_api_level():
    """Poziom API Androida (0 poza Androidem)."""
    if not _ANDROID:
        return 0
    try:
        from jnius import autoclass

        return autoclass("android.os.Build$VERSION").SDK_INT
    except Exception:
        return 0


def request_storage_permissions(callback=None):
    """Prosi o uprawnienia dostepu do plikow i powiadomien w runtime."""
    if not _ANDROID:
        return False
    try:
        from android.permissions import request_permissions

        if android_api_level() >= 33:
            perms = [
                "android.permission.READ_MEDIA_AUDIO",
                "android.permission.POST_NOTIFICATIONS",
            ]
        else:
            perms = ["android.permission.READ_EXTERNAL_STORAGE"]
        request_permissions(perms, callback)
        return True
    except Exception:
        return False


def storage_permission_granted():
    """Czy uprawnienie dostepu do plikow jest nadane."""
    if not _ANDROID:
        return True
    try:
        from android.permissions import check_permission, Permission

        if android_api_level() >= 33:
            return bool(check_permission(Permission.READ_MEDIA_AUDIO))
        return bool(check_permission(Permission.READ_EXTERNAL_STORAGE))
    except Exception:
        return False


def m3u_basenames(raw):
    """Wyciaga nazwy plikow (bez katalogow) z surowych bajtow .m3u."""
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1250", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        text = raw.decode("latin-1", errors="replace")
    names = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        base = os.path.basename(line.replace("\\", "/"))
        if base:
            names.append(base)
    return names


def find_media_paths(names):
    """Szuka plikow audio w MediaStore po nazwie (DISPLAY_NAME).

    Zwraca liste sciezek w tej samej kolejnosci co names (None gdy brak).
    Wymaga READ_MEDIA_AUDIO (API 33+) / READ_EXTERNAL_STORAGE (starsze).
    """
    if not _ANDROID or not names:
        return []
    try:
        from jnius import autoclass

        resolver = _activity().getContentResolver()
        MediaStoreAudio = autoclass("android.provider.MediaStore$Audio$Media")
        found = []
        for name in names:
            cursor = resolver.query(
                MediaStoreAudio.EXTERNAL_CONTENT_URI,
                ["_data"],
                "DISPLAY_NAME=?",
                [name],
                None,
            )
            path = None
            if cursor is not None:
                try:
                    if cursor.moveToFirst():
                        idx = cursor.getColumnIndex("_data")
                        if idx >= 0:
                            path = cursor.getString(idx) or None
                finally:
                    cursor.close()
            found.append(path)
        return found
    except Exception:
        return []


def pick_m3u(on_selected):
    """Natywny wybor pliku .m3u przez Intent (Android). Wymaga, by on_selected
    zostalo wywolane na watku glownym (uzyj Clock.schedule_once w callbacku).
    """
    if not _ANDROID:
        return False
    try:
        from android import activity, mActivity
        from jnius import autoclass, cast

        Intent = autoclass("android.content.Intent")
        String = autoclass("java.lang.String")
        from random import randint

        request_code = randint(123456, 654321)

        def on_result(request_code_, result_code, data):
            _dbg(
                "on_activity_result: fired, code=%s result=%s data=%s"
                % (request_code_, result_code, bool(data))
            )
            try:
                activity.unbind(on_activity_result=on_result)
            except Exception:
                pass
            if request_code_ != request_code:
                _dbg("on_activity_result: inny request_code, ignoruje")
                return
            try:
                if result_code != -1 or data is None:  # RESULT_OK == -1
                    _dbg("on_activity_result: anulowano (result=%s)" % result_code)
                    on_selected([])
                    return
                uri = data.getData()
                uri_str = uri.toString() if uri is not None else None
                _dbg("on_activity_result: uri=" + str(uri_str))
                if not uri_str:
                    on_selected([], "Brak wybranego pliku")
                    return
                path = resolve_playlist_path(uri_str)
                _dbg("on_activity_result: path=" + str(path))
                if path:
                    on_selected([path])
                else:
                    on_selected([], "Nie udało się odczytać wybranego pliku")
            except Exception as e:
                _dbg("on_activity_result: wyjatek " + repr(e))
                on_selected([], "Nie udało się odczytać wybranego pliku")

        activity.bind(on_activity_result=on_result)

        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType("*/*")
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        _dbg("pick_m3u: startActivityForResult request_code=%s" % request_code)
        mActivity.startActivityForResult(
            Intent.createChooser(
                intent,
                cast("java.lang.CharSequence", String("Wybierz plik .m3u")),
            ),
            request_code,
        )
        return True
    except Exception:
        return False
