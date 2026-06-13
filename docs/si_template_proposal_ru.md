# Единый DOCX-template для оформления SI

Оформление SI задается одним Word-файлом `SI_template.docx`.
Пользователь редактирует его как обычный будущий support: меняет шрифт,
жирность, курсив, интервалы, поля, нижние и верхние индексы прямо в Word.
Программа копирует это оформление и заменяет placeholder-ы на данные соединений.

## Правила placeholder-ов

Публичный формат единый: в placeholder-ах используются точки.

```text
{compound.name} ({compound.number})

{compound.preparation}

{reaction.loadings}

[{nmr.1h.label}] ({nmr.1h.conditions}) δ = {nmr.1h.peaks}.

[{nmr.13c.label}] ({nmr.13c.conditions}) δ = {nmr.13c.peaks}.

[{hrms.label}]: {hrms.adduct} calcd for {hrms.formula} {hrms.calculated}. Found {hrms.found}.

[{anal.label}] Calcd for {anal.formula}: {anal.calculated}. Found: {anal.found}.

[{ir.label}] ({ir.method}, cm-1): {ir.peaks}.
```

Если placeholder или группа placeholder-ов выделены жирным или курсивом, вставленный
текст наследует это форматирование. Квадратные скобки в `[{hrms.label}]` служат
только маркером форматируемой группы: в итоговом SI они удаляются.

## Reagent loadings

Отдельный `Compound_characterization` template больше не нужен. Текст загрузок
берется из того же `SI_template.docx`, из параграфа с loadings-placeholder-ами.

Пример:

```text
Alkene {number.Product} was obtained from bromide {number.Reagent.1} ({mg.Reagent.1} mg, {mmol.Reagent.1} mmol), {name.Reagent.2} ({mg.Reagent.2} mg, {mmol.Reagent.2} mmol), K2CO3 ({mg.K2CO3} mg, {mmol.K2CO3} mmol), AcOH ({uL.AcOH} µL, {mmol.AcOH} mmol) and MeCN ({mL.Solvent.MeCN} mL) according to GP2. Yield {yield.Product.mg} mg ({yield.Product.percent}); {appearance}; mp {mp} °C. Rf = {rf.value} ({rf.system}).
```

В самом Word-шаблоне формулы можно форматировать нормально: например, в `K2CO3`
цифры `2` и `3` должны быть нижними индексами.

## Важные placeholder-ы

- `{compound.name}`, `{compound.number}`, `{compound.preparation}`;
- `{reaction.loadings}`;
- `{number.Product}`, `{number.Reagent.1}`;
- `{name.Reagent.2}`, `{mg.Reagent.2}`, `{mmol.Reagent.2}`;
- `{mg.K2CO3}`, `{mmol.K2CO3}`;
- `{uL.AcOH}`, `{mmol.AcOH}`;
- `{mL.Solvent.MeCN}`;
- `{yield.Product.mg}`, `{yield.Product.percent}`;
- `{appearance}`, `{mp}`, `{rf.value}`, `{rf.system}`;
- `{nmr.1h.label}`, `{nmr.1h.conditions}`, `{nmr.1h.peaks}`;
- `{nmr.13c.label}`, `{nmr.13c.conditions}`, `{nmr.13c.peaks}`;
- `{hrms.label}`, `{hrms.adduct}`, `{hrms.formula}`, `{hrms.calculated}`, `{hrms.found}`;
- `{anal.label}`, `{anal.formula}`, `{anal.calculated}`, `{anal.found}`;
- `{ir.label}`, `{ir.method}`, `{ir.peaks}`.

Если ChemDraw недоступен для генерации `{name.Reagent.2}`, программа использует
fallback по формуле и пишет warning, но генерацию SI не останавливает.
