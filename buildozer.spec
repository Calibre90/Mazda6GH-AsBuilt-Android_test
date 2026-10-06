[app]
title = Mazda6GH As-Built TEST LITE
package.name = mazda6ghasbuilttest
package.domain = org.d3dimone
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,abt,txt,kv
icon.filename = %(source.dir)s/assets/icon.jpg
presplash.filename = %(source.dir)s/assets/presplash.jpg
version = 0.1
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0
android.api = 35
android.minapi = 26
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
