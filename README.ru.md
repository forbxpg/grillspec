# grillspec

**Spec-driven разработка с агентами: агент спрашивает, прежде чем угадывать.**

`pre-alpha` · [English version](README.md)

grillspec — библиотека скиллов и хуков для агентов. Прежде чем строить то, в чём
есть решение, агент грилит вас: по одному решению за раз, к каждому — рекомендуемый
ответ, при желании — совет независимых перспектив, пока угадывать станет нечего.
Затем он пишет спек, извлекает то, что стоит запомнить, пишет план и исполняет его
через TDD и ревью.

`grill → spec (+ memory) → plan → execute → archive`

Работает в **Claude Code, Cursor, Codex, Antigravity и GigaCode**; для хуков и CLI
нужен Python 3.11+. Спеки пишутся либо в формате, совместимом с OpenSpec (живые спеки
и дельты изменений), либо в стиле Superpowers (один дизайн-документ и один план на
изменение) — выбор делается для каждого проекта.

## Установка

| Агент | Команда |
|---|---|
| Claude Code | `claude plugin marketplace add forbxpg/grillspec && claude plugin install grillspec@grillspec` |
| Codex | `codex plugin marketplace add forbxpg/grillspec`, затем `/plugins` |
| Cursor | `/add-plugin forbxpg/grillspec` |
| Antigravity | `agy plugin install https://github.com/forbxpg/grillspec` |
| GigaCode | `uvx grillspec install --harness gigacode` |

Агент без системы плагинов: `uvx grillspec install --harness <имя> --copy`.
Затем попросите агента в проекте «set up grillspec».

## Документация

- English: [docs/en](docs/en)
- Русский: [docs/ru](docs/ru)

## Статус

Pre-alpha: фундамент (конфигурация, фазы, бутстрап, установщик) готов; скиллы гриля,
спека, плана и исполнения появляются по шагам. См. [CHANGELOG.md](CHANGELOG.md).

## Лицензия

MIT — см. [LICENSE](LICENSE). grillspec опирается на Superpowers, OpenSpec,
mattpocock/skills и claude-council; см. [NOTICE](NOTICE).
