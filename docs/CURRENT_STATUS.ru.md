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

## Обновление — 8 ноября 2026

- Повторно проверено присланное `bfrevive-V20.apk` из вложения. Проверка ZIP-CRC прошла, SHA-256 `libgame.so` совпадает с зафиксированным в `docs/BFREVIVE_V20_APK_AUDIT.md`.
- В рабочем контейнере адресный патчер создал неподписанный `bfrevive-V20-localhost-UNSIGNED.apk`; CRC архива и SHA-256 пропатченной `libgame.so` совпали с ожидаемым значением. **Это не установочный или играбельный APK**, сервер и контент в него ещё не встраивались.
- В `android-host` исправлен запуск `EmbeddedServerService` через `startForegroundService` на Android 8+. CI компиляции Android host + тестов успешно завершился.
- Следующая ошибка полной NDK-сборки выявила Glaze + анонимные структуры `EventRotation.cpp`, `Exchange.cpp`; в `tools/build_android_native.py` добавлено автоматическое безопасное для логики повышение видимости соответствующих DTO в **временной копии исходников**. Таким же способом обработаны другие известные DTO из `SummonRotation`, `UnitPick`, `NewsPosts`, `RaidRooms`, `TrialDeck`, `UnitOmniEvo`, `UnitSelectorGachaTicket`. Основная библиотека к моменту этого обновления **ещё компилировалась**; успешную `.so` не заявлять до прохождения Actions.
- Выделено ровно **126 различных названий decoded MST JSON**, непосредственно загружаемых из `ServerCache.cpp`; список: [required_mst_2_19_6.json](required_mst_2_19_6.json). Это минимальный базовый набор, а не гарантия полноты всех игровых ресурсов.
- Текущая native-сборка: https://github.com/Domenklay/BraveFrontier_Offline/actions/workflows/android-native-build.yml; хост-библиотека: https://github.com/Domenklay/BraveFrontier_Offline/actions/workflows/android-host.yml.

**По-прежнему не готово:** `libbf_offline_server.so`, локальный набор client `/content` и `/mst`, полноценное декодированное содержимое этих мастер-таблиц, устанавливаемый и проверенный Brave Frontier Offline APK. Без этих компонентов нельзя честно утверждать, что игра работает без интернета.

## Подтверждённый результат сборки сервера — 8 ноября 2026

- **NDK ARM64 C++ сервер собран успешно**: [GitHub Actions #42489519485](https://github.com/Domenklay/BraveFrontier_Offline/actions/runs/42489519485). Получена `libbf_offline_server.so`, архитектура `ELF64 AArch64`, исходный SHA256 `bd1afbf6bc7b0814df04056d2e33ae5aef0897cebe7b733eeca321f37f8aaab6`.
- Успешно проверена **отладочная очистка** этой же библиотеки: [GitHub Actions #42491727475](https://github.com/Domenklay/BraveFrontier_Offline/actions/runs/42491727475). Размер уменьшен с 853 708 192 до **40 764 640 байт**; SHA256 очищенной версии `d4d9b367c035c18fe365ffa749fb2a83c7899223c13fd9a21ded1660cc6cd898`.
- В `libbf_offline_server.so` присутствуют требуемые экспортируемые JNI-функции `runNativeServer` и `stopNativeServer`; в NEEDED остаются только стандартные Android `liblog.so`, `libdl.so`, `libm.so`, `libc.so`.
- Исходники сервера остаются в pinned upstream. В `tools/build_android_native.py` автоматизированы NDK-сборка, очистка отладочных секций и проверка JNI-символов.
- Реализован [сканер ресурсоёмких файлов LDPlayer](../tools/inventory_android_dump.py), который по сигнатурам определяет графику, звук, архивы и проверяет доступные декодированные MST. [Инструкция](LDPLAYER_RESOURCE_CAPTURE.ru.md). CI тестов Android-оболочки и сканера — успешно.

**Теперь главные блокеры:** локальная выгрузка полного набора клиентских `/content`, `/mst` и 126 декодированных MST; сборка одного подписанного APK с сервером; тест реального запуска в Android (включая работу без интернета, профиль, бои и сохранение). Native-библиотека **успешно скомпилирована, но не протестирована на устройстве**.
