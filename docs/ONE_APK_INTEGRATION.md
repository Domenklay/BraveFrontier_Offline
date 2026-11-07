# Попытка упаковки оригинального Brave Frontier + готового сервера в один APK

**Статус: экспериментальная интеграция в `main` и ветке `feature/embedded-server-bootstrap`.** Реальный оригинальный APK с встроенным сервером пока не собран и не протестирован.

## Что сделано

1. `android-host/host/src/main/java/...` — Android-служба, bootstrap-provider и стартовая Activity: сперва запускает настоящий localhost-сервер и ожидает его JSON-ответ на `/dls`, лишь затем открывает исходную Activity игры.
2. `android-host/native/NativeServer.cpp` — JNI entry point, перенесённый по логике upstream `standalone_frontend/main.cpp`: работает с реальным Drogon, SQLite миграциями и балансом.
3. `tools/build_android_native.py` — конфигурация порта существующего C++ сервера в `libbf_offline_server.so` для Android arm64, без переписывания серверной логики.
4. `tools/stage_payload.py` — подготовка реальных существующих серверных данных, клиентских таблиц и ресурсов в файлы APK (ничего не скачивает и не подделывает).
5. `tools/inject_host.py` — склейка модифицированного ОРИГИНАЛЬНОГО APK, скомпилированного Android host AAR, настоящей серверной .so и данных, с повторной подписью.
6. `android-host` — Android library, **не новая игра и не отдельный игровой APK**.

## Поток запуска

```text
sg.gumi.bravefrontier (тот же APK, оригинальная package identity)
  -> OfflineBootstrapProvider.onCreate()
      -> startService(EmbeddedServerService) в процессе :bfserver
          -> распаковка bundled assets/bf-offline/* во внутреннюю files/bf_offline/
          -> System.loadLibrary("bf_offline_server")
          -> runNativeServer(.../config.json)
              -> настоящие маршруты Drogon: /dls, /bf/gme/action.php,
                 /mst, /content и другие
              -> app-private SQLite gme.sqlite
  -> OfflineLaunchActivity (стартовый экран внутри исходного APK)
      -> опрашивает НАСТОЯЩИЙ GET /dls, никаких имитированных ответов
      -> после ответа открывает оригинальную Activity клиента
  -> оригинальный клиент обращается к 127.0.0.1:9960
```

Отдельный процесс выбран сознательно: upstream `main.cpp` меняет текущую директорию процесса, а сервер может падать отдельно от игрового движка. Игра и сервер находятся в **одном установленном APK и на одном телефоне**.

### Известные недоработки

- C++23 сервер ещё не проверен на успешную NDK сборку и загрузку в Android. Первая реальная CMake-конфигурация выявила некорректные выражения переменных в JNI CMakeLists.txt; ошибка исправлена, выполняется повторная проверка.
- Новый launcher ожидает HTTP 200 и настоящий JSON `/dls` перед открытием оригинальной Activity. Нужно проверить, не отправляет ли оригинальный `Application.onCreate()` сетевые запросы ещё до этой Activity, и протестировать загрузку больших ресурсов.
- Не проверены все загрузочные файлы, декодированные MST и работа клиентских экранов.
- Отдельно надо проверить вызовы Android cleartext/loopback, многопроцессность, перезапуск, память, Android 12–16 ограничения на фоновые службы.
- Извлечение нескольких ГБ данных в приватное хранилище может быть долгим и потребовать много свободного места. Один большой APK может упереться в ограничения установки; способ поставки будет зависеть от размера реального пакета.
- `apktool` может менять исходные ресурсы манифеста; нужен дифф и установочный тест на настоящем APK.
- Успешный компилятор AAR лишь подтверждает Java-часть мостика.

## Сборка при наличии личной совместимой копии клиента и игровых ресурсов

Входной файл BF Revive V20 **уже получен и проанализирован**. Для дальнейшей сборки необходимы: Git, Python 3, JDK 17, CMake 4+, Ninja, Rust, Android SDK/NDK, vcpkg, Gradle 8.10.2, apktool, d8, zipalign, apksigner, свой keystore. Ресурсы клиентского APK и правовой статус их использования проверяются отдельно.

```bash
python tools/sync_upstream.py

# ВАРИАНТ A: присланный BF Revive V20 (точная byte-checked версия).
python tools/patch_bfrevive_v20.py /private/bfrevive-V20.apk \
  --unsigned-apk build/patched-client.apk

# ВАРИАНТ B: чистый оригинальный клиент, с другим SHA256
# (не использовать для фанатского APK):
# python tools/check_client.py /private/BraveFrontier_2.19.6.apk
# python upstream/server/tools/patch_apk.py \
#   --apk /private/BraveFrontier_2.19.6.apk \
#   --out build/patched-client.apk --host 127.0.0.1:9960

# Здесь нужны отдельно сохранённые оригинальные content/mst и decoded tables.
python tools/stage_payload.py \
  --content-root /private/client-downloads \
  --decoded-mst /private/decoded-client-mst

# Экспериментальная сборка исходного C++-сервера для Android:
python tools/build_android_native.py \
  --ndk /opt/android-sdk/ndk/27.2.12479018 --vcpkg /opt/vcpkg

cd android-host
gradle :host:assembleRelease
cd ..

# BF_OFFLINE_KS_PASS должен быть установлен в окружении.
python tools/inject_host.py \
  --patched-apk build/patched-client.apk \
  --host-aar android-host/host/build/outputs/aar/host-release.aar \
  --native-lib android-host/host/src/main/jniLibs/arm64-v8a/libbf_offline_server.so \
  --payload build/offline-payload \
  --android-jar /opt/android-sdk/platforms/android-35/android.jar \
  --keystore /private/bf-offline.jks --key-alias bf-offline \
  --output build/BraveFrontier-offline-experimental.apk
```

Перед тестом сохранить локальные данные оригинального приложения. Из-за другой подписи его может потребоваться удалить перед установкой модифицированной версии; удаление может стереть прогресс.

## Как проверим

- APK устанавливается и открывает **оригинальную игру**, не Java-макет.
- В `adb logcat` есть запуск `BF-Offline` и `BF-Offline-Native`.
- Ответ `GET http://127.0.0.1:9960/dls` приходит из телефона.
- В авиарежиме есть создание профиля, загрузка персонажей, вход в сюжет, реальный бой и сохранение после полного перезапуска.
- Весь исходящий сетевой трафик ограничен localhost — необходимо тестирование, а не только отсутствие внешних адресов в конфиге.

Android разрешение `INTERNET` нужно даже для loopback сокета; оно не является обязательством использования сети интернет.

## Лицензии

Портировать сервер AGPL-3.0 и публиковать соответствующие исходники при требуемом распространении. Оригинальные APK/ресурсы не загружать в GitHub без прав.
