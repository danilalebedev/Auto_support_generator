# Установка Auto Support Generator beta 1.2

## Что установить заранее

- Windows 10 или 11, 64-bit;
- Microsoft Word desktop;
- ChemDraw/ChemOffice с поддержкой OLE;
- MestReNova.

Проверенные версии: ChemDraw `22.2.0.3300`, MestReNova `14.2.0-26256`. Используйте [официальную инструкцию загрузки ChemDraw](https://support.revvitysignals.com/hc/en-us/articles/4408210538132-How-do-I-download-the-MSI-installer-for-ChemDraw) и [официальную страницу загрузки Mnova](https://mestrelab.com/download). Обе программы требуют собственной действующей лицензии и не входят в установщик. Python для готовой сборки не нужен.

## Установка

1. На странице GitHub Release `Auto_support_generator_beta.1.2` скачайте `AutoSupportGeneratorSetup.exe`.
2. Запустите скачанный файл.
3. После сообщения об успешной установке откройте **Auto Support Generator** с рабочего стола или из меню Пуск.
4. Перед первой генерацией один раз вручную запустите Word, ChemDraw и MestReNova.

Программа устанавливается для текущего пользователя в:

```text
%LOCALAPPDATA%\AutoSupportGenerator
```

Установщик не загружает Python или химические программы из интернета и не требует прав администратора.

## Примеры

В установленной папке находятся три полных набора:

```text
examples\example_1
examples\example_2
examples\example_3
```

Каждый набор использует те же названия, что и поля GUI:

- `Compound_table.docx`;
- `Spectra_source` или `Spectra_source.zip`;
- `SI_template.docx`;
- `Reaction_schema.docx`;
- `Scope.docx`.

Примеры также можно скопировать из раздела **Instructions → Example files**.

## Первый запуск

1. На странице **Generate** выберите `Compound_table.docx`.
2. В **Spectra source** выберите zip или папку со спектрами.
3. Выберите **Output folder**.
4. При необходимости укажите SI template, отдельные 1H/13C `.mngp`, Reaction schema и Scope.
5. Проверьте настройки на странице **Processing**.
6. Нажмите **Generate SI**.

Подробное описание всех функций находится в `README_RU.md` и внутри страницы **Instructions** приложения.

## Контакты

- Email: [lebedevdanilaaa@gmail.com](mailto:lebedevdanilaaa@gmail.com)
- Telegram: [@lebdanchem](https://t.me/lebdanchem)

При обращении приложите `support_information.run_summary.json` и папку `logs` проблемного запуска.

## Если программа не запускается

- Убедитесь, что файл скачан из официального репозитория и не заблокирован Windows.
- Проверьте, что Word, ChemDraw и MestReNova запускаются вручную.
- Если MestReNova не найдена, укажите путь к `MestReNova.exe` в Generate.
- Откройте папку `logs` последнего запуска для подробной диагностики.
