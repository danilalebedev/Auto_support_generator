# Reaction and compound scope

## Пример

Четыре бромида 2a–2d из `example_1`. Исходные ChemDraw-структуры и измеренные массы сохранены без изменений.

1. В Generate выберите **Single all-in-one DOCX** и `All_in_one_input.docx` из этой папки.
2. Включите **Show scope**. Заголовок: `Synthesis of bromides`.
3. В **Reaction conditions** можно ввести температуру и время. В этом примере поле оставлено пустым: эти значения не заданы во входных таблицах. Растворитель CHCl3 берётся из Reaction schema.
4. При обычной полной сборке выберите также `Spectra_source` из `examples/example_1`.

`Reference_output.docx` — демонстрационная сборка **без повторной обработки ЯМР**. Она показывает реакцию, scope, рассчитанные загрузки и доступные табличные аналитические данные, но не заменяет полный SI со спектрами. `reaction_scope_1.cdxml` остаётся редактируемым, а `reaction_scope_1.png` показывает тот же рисунок, вставленный в Word.

Верхняя реакция показывает конкретный первый продукт серии, а не автоматически выдуманную обобщённую структуру с R-группой. Служебная подпись `Representative reaction` не выводится. Постоянные реагенты показаны над стрелкой без эквивалентов, растворитель и введённые условия под стрелкой. Далее идут разделительная линия и структуры; подпись под каждой структурой имеет вид **2a**, 80%, где только номер соединения выделен жирным.

## Результат

- `Reference_output.docx`: scope перед описаниями соединений.
- `reaction_scope_1.cdxml`: редактируемый рисунок для ChemDraw.
- `reaction_scope_1.png`: нативное изображение ChemDraw, вставленное в Word.

Полная папка реального запуска дополнительно содержит `scope_graphic.json`, manifest, logs и input-копии; именно её следует сохранять для последующих Patch/Add.

При Patch номера, порядок и состав scope обновляются по идентификаторам соединений без обработки спектров. При Add To Same Series scope расширяется; New Method получает отдельную схему. В новой методике температуру и время предыдущей серии автоматически не копируем.

Для генерации и обновления рисунка нужен установленный лицензированный ChemDraw. Снятая галочка не создаёт scope и не запускает его генератор. Одновременно должна обрабатываться одна задача ChemDraw.

## Воспроизведение демонстрации

```powershell
.venv\Scripts\python.exe -m si_generator `
  --all-in-one-input examples/reaction_scope/All_in_one_input.docx `
  --show-scope --scope-title "Synthesis of bromides" `
  --no-extract-nmr --insert-spectra-as none `
  --output output/reaction_scope/support_information.docx
```

Алгоритмы MCS-выравнивания и переноса Ring Fill адаптированы из авторского ChemStyleGrid. CDX/CDXML читает и визуализирует нативный ChemDraw; пакет PyCDXML и его benchmark-зависимости не включены в Auto Support Generator.
