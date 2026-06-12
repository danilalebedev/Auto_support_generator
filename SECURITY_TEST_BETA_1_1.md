# Security Test: Auto Support Generator beta.1.1

Дата проверки: 2026-06-12.

## Проверенная область

Проверены релизные изменения и основные risk points программы:

- installer и создание ярлыков;
- обработка zip/papka spectra source;
- запуск внешних программ Word, ChemDraw и MestReNova;
- операции с файлами в output/logs;
- поиск секретов и подозрительных сетевых адресов;
- наличие опасных shell-вызовов.

## Результат

Критичных проблем, из-за которых программу нельзя давать коллегам для beta
тестирования, не найдено.

## Что проверено и исправлено

### Installer / desktop shortcut

Проблема: ярлык на рабочем столе мог создаваться с пустым `TargetPath`, поэтому
открывал рабочий стол вместо GUI.

Исправление:

- shortcut создается через временный PowerShell `.ps1`;
- параметры передаются как `-AppDir` и `-ExePath`, а не неявно через
  `-Command`;
- после сохранения shortcut проверяется, что `TargetPath` совпадает с
  `AutoSupportGenerator.exe`;
- installer теперь падает с ошибкой, если ярлык не удалось создать корректно.

### Zip extraction

Уже была защита от path traversal: файлы из zip не могут распаковаться за
пределы рабочей папки.

Добавлено:

- лимит количества файлов в zip: `20 000`;
- лимит общего распакованного размера: `2 GB`;
- regression test на `../escape/fid`.

Это снижает риск случайного или злонамеренного zip-bomb.

### Spectra folder input

Добавлена поддержка обычной папки вместо zip. Папка не копируется целиком
сразу, а используется как источник путей к raw Bruker experiments. Для
MestReNova каждый спектр затем staging-копируется в служебную ASCII-папку,
как и раньше.

### External programs

Программа запускает только ожидаемые локальные desktop-программы:

- `AutoSupportGenerator.exe` из установленной папки;
- Microsoft Word через COM;
- ChemDraw/ChemSketch через OLE/COM;
- MestReNova через найденный `MestReNova.exe`.

Вызовы `subprocess` используют списки аргументов, не `shell=True`. Это снижает
риск shell injection при путях с пробелами или спецсимволами.

### File operations

Удаления через `shutil.rmtree` ограничены служебными директориями, которые
создает сама программа:

- временная папка Mnova staging;
- `logs/_spectra_zip`;
- `processed_spectra`;
- папка examples при переустановке.

Опасных операций вида удаления произвольного пользовательского пути не найдено.

### Secrets / network

Поиск по ключевым словам `token`, `secret`, `password`, `api_key`, приватным
ключам и внешним URL не выявил встроенных секретов. Программа не делает сетевых
запросов в runtime; ссылки в документации не являются runtime-интеграциями.

## Оставшиеся ограничения beta

- Программа доверяет локально установленным Word/ChemDraw/MestReNova. Если одна
  из этих программ повреждена или подменена, Auto Support Generator не может это
  проверить.
- Входные `.docx` и raw spectra должны приходить из доверенного источника.
  Особенно это важно для документов с OLE-объектами.
- Очень большие raw spectra могут долго обрабатываться MestReNova; zip-bomb
  ограничен, но обычная папка не имеет общего лимита размера.
- Installer пишет в `%LOCALAPPDATA%\AutoSupportGenerator` и создает ярлыки на
  рабочем столе и в Start Menu.

## Запущенные проверки

```powershell
$env:PYTHONPATH='C:\Users\user\Desktop\Auto_support_generator_beta_1_1_release\src'
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\.venv\Scripts\python.exe -m unittest discover -s tests
git diff --check
rg -n "shell=True|subprocess\.|Popen\(|os\.system|eval\(|exec\(|pickle|yaml\.load|rmtree|ZipFile|extract\(|extractall" src scripts -S
rg -n "password|token|secret|credential|api[_-]?key|PRIVATE|BEGIN RSA" . -S
```

Regression tests: `6` tests passed.

Installer smoke test:

```powershell
$p = Start-Process -FilePath '.\installer\AutoSupportGeneratorSetup.exe' -ArgumentList '--quiet' -Wait -PassThru
$p.ExitCode
```

Result: `0`. After installation, desktop shortcut target was:

```text
C:\Users\user\AppData\Local\AutoSupportGenerator\AutoSupportGenerator.exe
```

Working directory was:

```text
C:\Users\user\AppData\Local\AutoSupportGenerator
```
