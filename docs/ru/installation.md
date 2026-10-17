# Установка

grillspec нужен **Python 3.11 или новее** на машине, где работает агент: хуки и CLI
написаны на Python, только стандартная библиотека. Без него grillspec всё равно
устанавливается и скиллы загружаются, но хуки вместо статуса сессии сообщают «gates are
OFF» (см. [Как работает бутстрап](how-it-works/bootstrap.md)).

## По агентам

| Агент | Установка | Обновление |
|---|---|---|
| Claude Code | `claude plugin marketplace add forbxpg/grillspec`, затем `claude plugin install grillspec@grillspec` | `claude plugin update grillspec@grillspec` |
| Codex | `codex plugin marketplace add forbxpg/grillspec`, затем выбрать grillspec в `/plugins`; доверить его хукам в `/hooks` | `/plugins` |
| Cursor | `/add-plugin forbxpg/grillspec` | менеджер плагинов Cursor |
| Antigravity | `agy plugin install https://github.com/forbxpg/grillspec` | повторить установку |
| GigaCode | `uvx grillspec install --harness gigacode` | повторить установку |

Codex запускает хуки плагина только после того, как вы доверите им в `/hooks`. До этого
роутер всё равно подгружается по описанию скилла — пропадает только строка статуса.

## Без системы плагинов

Запасной установщик копирует скиллы в каталог скиллов агента и записывает каждый
созданный файл:

```bash
uvx grillspec install --harness gigacode                 # проект: .gigacode/skills
uvx grillspec install --harness codex --copy --scope user  # пользователь: ~/.agents/skills
uvx grillspec install --harness gigacode --dry-run       # показать записи, ничего не менять
```

Для агентов с плагинами `install` печатает нативную команду, если не передан `--copy`.
Для GigaCode он ещё добавляет одну строку импорта в `GIGACODE.md`, чтобы роутер
загружался в каждой сессии.

## Удаление

```bash
uvx grillspec uninstall --harness gigacode
```

`uninstall` удаляет ровно те файлы и строку импорта, которые `install` записал в
`.grillspec/install-receipt.json` (или в пользовательскую квитанцию рядом с
пользовательским конфигом). Ваши правки в `GIGACODE.md` остаются.

## Настройка проекта

Попросите агента «set up grillspec in this repo». Скилл `init` порекомендует бэкенд
спеков, покажет каждое изменение ваших файлов и запишет их только после вашего «да».
То же из терминала:

```bash
grillspec detect
grillspec init --backend openspec --dry-run
grillspec init --backend openspec
```
