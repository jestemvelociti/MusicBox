[app]
title = MusicBox
package.name = musicbox
package.domain = org.musicbox

source.dir = .
source.include_exts = py,kv,atl
source.include_patterns = assets/*.png

version = 0.5.1

requirements = hostpython3==3.11.9,python3==3.11.9,kivy==2.3.0,kivymd==1.2.0,pyjnius,plyer,mutagen,pillow

p4a.branch = develop
p4a.update = False

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_AUDIO,MANAGE_EXTERNAL_STORAGE,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PLAYBACK,POST_NOTIFICATIONS,WAKE_LOCK
android.add_src = java
android.wakelock = True
android.allow_backup = True
android.accept_sdk_license = True
android.icon = assets/icon.png
android.presplash_color = #0a0f1e
android.presplash = assets/icon.png
android.install_locations = auto

[buildozer]
log_level = 2
warn_on_root = 1
