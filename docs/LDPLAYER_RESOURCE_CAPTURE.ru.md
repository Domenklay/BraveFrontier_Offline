# Выгрузка ресурсов Brave Frontier из LDPlayer 9

Цель: выгрузить скачанные BF Revive V20 файлы и определить, какие из них нужны локальному серверу. Не публиковать архив с оригинальной игрой или персональными данными.

## До выгрузки

1. Дождаться установки LDPlayer 9 (64-bit) и загрузки клиентом основных игровых данных. Не очищать кэш и не удалять игру.
2. Проверить реальный путь к adb.exe и серийный номер эмулятора через команду `adb devices -l`.
3. По мере необходимости открыть меню персонажей, призыв, несколько локаций и боевые экраны — часть ресурсов игра загружает только по запросу.
4. Сначала осмотреть каталоги; копировать только то, к чему есть легальный доступ, и не выгружать секреты авторизации.

## Команды ADB (использовать реальный путь к LDPlayer)

```powershell
# adb.exe ниже — пример; замените на путь от своего LDPlayer 9
& 'C:\LDPlayer\LDPlayer9\adb.exe' devices -l
& 'C:\LDPlayer\LDPlayer9\adb.exe' shell getprop ro.product.cpu.abilist
& 'C:\LDPlayer\LDPlayer9\adb.exe' shell pm path sg.gumi.bravefrontier
& 'C:\LDPlayer\LDPlayer9\adb.exe' shell ls -la /sdcard/Android/data/sg.gumi.bravefrontier
& 'C:\LDPlayer\LDPlayer9\adb.exe' shell ls -la /sdcard/Android/obb/sg.gumi.bravefrontier
```

При нескольких эмуляторах указывать `-s <serial>` перед командой `shell` или `pull`.

```powershell
New-Item -ItemType Directory -Force C:\BF_Archive
& 'C:\LDPlayer\LDPlayer9\adb.exe' pull /sdcard/Android/data/sg.gumi.bravefrontier C:\BF_Archive\AndroidData
& 'C:\LDPlayer\LDPlayer9\adb.exe' pull /sdcard/Android/obb/sg.gumi.bravefrontier C:\BF_Archive\OBB
```

Если какой-то каталог не существует, это не повод создавать его или очищать приложение. Приватный каталог `/data/data/sg.gumi.bravefrontier` требует root и содержит аккаунт, токены и пользовательские настройки; не загружать его целиком в общий архив.

## Локальная инвентаризация файлов

```powershell
python tools/inventory_android_dump.py --root 'C:\BF_Archive\AndroidData' --root 'C:\BF_Archive\OBB' --out 'C:\BF_Archive\bf_inventory.json'
```

Скрипт не подключается к сети, не пересылает и не копирует исходные файлы. Он определяет типы PNG/JPEG/WebP/OGG/ZIP и неизвестных контейнеров, размеры, а также наличие декодированных MST JSON по списку `docs/required_mst_2_19_6.json`.

Если отсутствует OBB, исключить соответствующий аргумент `--root`. Список имён и относительных путей в итоговом JSON следует проверить перед передачей. Проверка содержимого не доказывает, что полный архив игры уже загружен.

После получения и проверки инвентаризации следующий этап — сопоставить содержимое с 126 MST и ресурсами `/mst` и `/content`, затем собирать локальный payload для встроенного C++-сервера.
