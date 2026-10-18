# grillspec

**Spec-driven разработка с агентами: агент спрашивает, прежде чем угадывать.**

`0.1.0` · [English version](README.md)

grillspec — библиотека скиллов и хуков для агентов. Прежде чем строить то, в чём
есть решение, агент грилит вас: по одному решению за раз, к каждому — рекомендуемый
ответ, при желании — совет независимых перспектив, пока угадывать станет нечего.
Затем он пишет спек, извлекает то, что стоит запомнить, пишет план и исполняет его
через TDD и ревью.

`grill → spec (+ memory) → plan → execute → archive`

Работает в **Claude Code, Cursor, Codex, Antigravity и GigaCode**, на Linux, macOS и
Windows; для хуков и CLI нужен Python 3.11–3.15 (находится автоматически). Спеки пишутся либо в формате, совместимом с OpenSpec (живые спеки
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

## Поддержка

| Харнесс | Статус | Проверено |
|---|---|---|
| Claude Code | поддерживается | бутстрап и ворота проходят smoke-прогоны |
| Cursor | поддерживается | бутстрап и ворота проходят smoke-прогоны (`cursor-agent`) |
| Codex | не проверен | хукам нужно одобрение через `/hooks` после каждого обновления плагина |
| Antigravity | не проверен | ворота поставляются выключенными до smoke-теста |
| GigaCode | экспериментальный | хуков нет; воротами служат скиллы |

## Данные и приватность

grillspec не собирает персональные данные и не держит собственного сервиса: CLI и хуки
работают с файлами вашего проекта. Отправляет данные наружу только одна функция —
**council**. Когда гриль его использует (`council.enabled` по умолчанию `ask`, то есть
вас спрашивают каждый раз), вопрос и его контекст уходят промптом в агентские CLI,
установленные и залогиненные на вашей машине (`claude`, `codex`, `cursor-agent`,
`gemini`, `agy`, `gigacode`), под вашими же аккаунтами у этих вендоров.
`council.external = "never"` оставляет в council только локальных субагентов. См.
[Как работает council](docs/ru/how-it-works/council.md).

## Документация

- English: [docs/en](docs/en/README.md)
- Русский: [docs/ru](docs/ru/README.md) — зачем нужен каждый механизм и как он работает
- Цена в токенах: [docs/ru/tokens.md](docs/ru/tokens.md) — около 2 100 токенов на сессию
  в Claude Code (измерено) плюс блок памяти вашего проекта; остальное — только когда
  скилл используется

## Статус

0.1.0, первый публичный релиз: гриль, council, спеки, память, планы, выполнение, архив
и ворота между фазами. В версиях 0.x форматы ещё могут меняться; changelog об этом
сообщает. См. [CHANGELOG.md](CHANGELOG.md).

## Лицензия

MIT — см. [LICENSE](LICENSE). grillspec опирается на Superpowers, OpenSpec,
mattpocock/skills и claude-council; см. [NOTICE](NOTICE).
