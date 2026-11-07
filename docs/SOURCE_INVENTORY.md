# Brave Frontier: инвентаризация исходников (7 ноября 2026)

Проверено непосредственно по README, исходным файлам и структуре открытых GitHub-репозиториев.

| Компонент | Где лежит | Что реально можно взять | Чего не хватает |
|---|---|---|---|
| Оригинальная серверная эмуляция | [joppe2001/bf-private-server](https://github.com/joppe2001/bf-private-server) | C++23, Drogon, SQLite, десятки игровых систем, 221 регистрация запроса, старт, логин, бои, призыв, события | Готовой сборки для Android NDK и ряда обработчиков |
| Серверные JSON | [joppe2001/bf-private-server-data](https://github.com/joppe2001/bf-private-server-data) | archive/: ai, mission, unit, gacha, дропы и др. (18 JSON по текущей корневой структуре) | Клиентские mst таблицы и загружаемые ресурсы |
| Патч оригинального клиента | [joppe2001/bf-private-server/tools/patch_apk.py](https://github.com/joppe2001/bf-private-server/blob/main/tools/patch_apk.py) | Точные byte-patches версии 2.19.6, HTTPS/HTTP, адрес сервера, подпись APK | Сам оригинальный APK, совместимость патча с иной версией не гарантирована |
| Ранний эмулятор | [decompfrontier/server](https://github.com/decompfrontier/server) | Экспериментальный C++ эмулятор; основа форка | Недостающие функции, Android порт |
| Ранние офлайн-патчи | [decompfrontier/offline-diff](https://github.com/decompfrontier/offline-diff) | xdelta-патчи .so, localhost 127.0.0.1:9960 | Оригинальные .so, сервер и ресурсы |
| Декомпиляция клиента | [decompfrontier/client](https://github.com/decompfrontier/client) | Неполная структура src/android + src на C++ | Автор прямо предупреждает: проект может не собираться; полного восстановленного APK нет |
| Архив исследовательских данных | [BluuArc/bfmt-data](https://github.com/BluuArc/bfmt-data) | Datamine для units, skills, items и т. п. | Не замена оригинальным клиентским таблицам и текстурам |

## Устройство bf-private-server

- server/gimuserver/ — настоящий C++ игровой сервер и контроллеры.
- server/standalone_frontend/main.cpp — запускает Drogon, SQLite миграции и загрузку баланса.
- server/packet-generator/ — Rust генератор C++ схем сообщений.
- server/deploy/config.json — listener 127.0.0.1:9960, SQLite, пути к client MST, server system/archive и загрузочным ресурсам.
- tools/patch_apk.py — патчер **собственного** клиентского APK 2.19.6.
- data-репозиторий: archive/ — восстановленные серверные данные.

Зависимости для компиляции сервера (server/vcpkg.json): **Drogon, Crypto++, SQLite3, Glaze**, дополнительно пакетный Rust генератор.

## Три разных вида данных

1. **Curated server archive:** готовый восстановленный JSON — есть в bf-private-server-data.
2. **Decoded client MST:** JSON-таблицы вроде unit_mst.json, area_mst.json — **нет** в открытых серверных GitHub репозиториях, нужны отдельно.
3. **Client content:** изображения, звук, шрифты, игровые таблицы /content и /mst — **нет** в серверных репозиториях, нужны отдельно.

Наличие исходников эмулятора **не равно** наличию полных исходников оригинального игрового клиента, и не равно готовому Android APK.

## Лицензирование и распространение

C++ сервер — AGPL-3.0; при интеграции его кода сохранить уведомления, исходники и выполнять лицензионные условия. Оригинальная игра и её контент принадлежат правообладателям. Собранный пакет с ними не публиковать без законных прав.
