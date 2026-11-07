# Текущее состояние проекта — 7 ноября 2026

**Не переписывать Brave Frontier с нуля.** Использовать оригинальный BF Revive V20 (Global 2.19.6) и уже существующий C++23 эмулятор сервера.

## Подтверждённые материалы

- Пользователь предоставил `bfrevive-V20.apk`. Package: `sg.gumi.bravefrontier`, original Activity: `sg.gumi.bravefrontier.BraveFrontier`, versionName 2.19.6.0, ARM64. Файл и его `libgame.so` **не коммитить в GitHub**.
- SHA256 `libgame.so`: `b7e856193c378edd17ac12b0551e001535454d112c9e4e346e83d3bd934e0281`.
- Успешно проверены 9 guarded byte patches (адреса API и CDN -> 127.0.0.1:9960, HTTPS -> HTTP). Новый SHA256 `libgame.so`: `37dd87af1e64f115882d23aa11b525a915e1f84e99fe2798d26ba4c55b7e5af5`.
- Локальная промежуточная неподписанная копия APK прошла ZIP-CRC и SHA-проверки. **Не устанавливать**: сервер ещё не встроен.
- `joppe2001/bf-private-server`: pinned commit `f9d0b5a324ecb517e257d8d0c39413840caa851b`, AGPL-3.0.
- `joppe2001/bf-private-server-data`: pinned commit `480a8e4f78e13b1501ca77adc5b50090a8405983`.
- Сервер запрашивает 126 уникальных decoded MST JSON в ServerCache.cpp. Кроме них требуются архивы /content и /mst; присланный APK содержит лишь базовые ресурсы (около 30.8 MiB в assets/).

## Уже создано

- `tools/patch_bfrevive_v20.py`: точный патчер присланного APK.
- `android-host/`: Java служба в процессе :bfserver, FGS, bootstrap-provider, ожидание настоящего /dls перед открытием исходной Activity.
- `android-host/native/NativeServer.cpp`: JNI адаптер **оригинального** C++ сервера, Drogon/SQLite, без имитации геймплея.
- `tools/build_android_native.py`: перенос готового C++ кода на Android NDK arm64 через vcpkg.
- `tools/stage_payload.py`: локальная упаковка server system/archive + decoded MST + client content с SHA256 и явным localhost DLS; не принимает неполный базовый набор таблиц.
- `tools/audit_content.py`: перечень отсутствующих серверу клиентских JSON и размеров локального архива.
- `tools/inject_host.py`: упаковка оригинального пропатченного APK с Android AAR, native .so и ресурсами; подписывает своим ключом.
- `tools/tests/`: тесты инъекции манифеста, архитектуры native .so, V20-патча, упаковки и схем данных.
- root LICENSE (AGPL-3.0), NOTICE.md, документация.

## Проверки

- Android host AAR собирается: **да**, CI прошёл.
- Синтаксис Python и unit tests: **да**, CI прошёл.
- Android NDK CMake конфигурация полного сервера: **да**, CI прошёл.
- Полная Android NDK компиляция:
  1. Первый прогон остановился на отсутствующих типах пакетов в JNI TU — исправлено include upstream App.hpp и зависимость pkgen_generate.
  2. Второй прогон остановился на конфликте host clang-scan-deps и NDK Clang PCH — добавлено CMAKE_CXX_SCAN_FOR_MODULES OFF и CXX_SCAN_FOR_MODULES OFF на JNI target.
  3. **Следующий прогон инициирован**, результат необходимо проверить по GitHub Actions, не считать заранее успешным.
- Установочный APK с настоящей игрой + встроенным сервером: **ещё нет**.
- Запуск в авиарежиме: **не проверен**.

## Ссылки на CI

- Android host: https://github.com/Domenklay/BraveFrontier_Offline/actions/workflows/android-host.yml
- NDK full native build: https://github.com/Domenklay/BraveFrontier_Offline/actions/workflows/android-native-build.yml

## Следующий порядок работ

1. Проверить последний результат full native build. При успехе получить `libbf_offline_server.so`; при ошибке исправлять только реальные причины из логов, не переписывать сервер.
2. Найти/подготовить отдельно полученные decoded MST + /content + /mst, проверить `tools/audit_content.py` (127 ссылок / 126 уникальных таблиц — базовый список, не гарантия полной совместимости).
3. Объединить пользовательский V20 APK, библиотеку сервера и данные через `tools/inject_host.py`, проверить подпись и установку.
4. Тестировать /dls, логин, битву, сохранения **в авиарежиме**, затем вычищать внешние зависимости (если есть).
5. Только потом собственные существа и игровые режимы через upstream balance overlays.

В исходной форме server + APK **невозможно** назвать полноценной офлайн-версией без ресурса MST и контентного архива; не обещать готовый APK до тестов.
