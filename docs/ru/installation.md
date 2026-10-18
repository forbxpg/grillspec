# Установка

grillspec нужен **Python 3.11 или новее** (от 3.11 до 3.15) на машине, где работает
агент: хуки и CLI написаны на Python, только стандартная библиотека. Без него grillspec
всё равно устанавливается и скиллы загружаются, но хуки вместо статуса сессии сообщают
«gates are OFF» (см. [Как работает бутстрап](how-it-works/bootstrap.md)).

## Какой Python используется

На машине часто несколько версий Python, и `python3` — не всегда самая новая, а на
Windows и вовсе может быть не настоящим Python. grillspec никогда не вызывает `python3`
вслепую. Его лаунчеры (`scripts/grillspec` на Linux и macOS, `scripts/grillspec.cmd` на
Windows) берут первого кандидата версии 3.11 или новее:

1. исполняемый файл из `GRILLSPEC_PYTHON`, если переменная задана;
2. на Linux и macOS: `python3.15` … `python3.11`, затем `python3`, `python`, затем
   лаунчер `py` (он есть под Git Bash на Windows);
3. на Windows: `py -3.15` … `py -3.11`, затем `python3`, `python`;
4. `uv run --python ">=3.11"`, если установлен `uv`, — он сам скачает Python, если
   подходящего нет.

Машина только с Python 3.14 или со старым `python3` рядом с более новым `python3.13`
работает без настройки. Закрепить конкретный: `export GRILLSPEC_PYTHON=/путь/к/python`
(PowerShell: `$env:GRILLSPEC_PYTHON = "C:\Path\To\python.exe"`).

## По агентам

| Агент | Установка | Обновление |
|---|---|---|
| Claude Code | `claude plugin marketplace add forbxpg/grillspec`, затем `claude plugin install grillspec@grillspec` | `claude plugin update grillspec@grillspec` |
| Codex | `codex plugin marketplace add forbxpg/grillspec`, затем выбрать grillspec в `/plugins`; доверить его хукам в `/hooks` | `/plugins` |
| Cursor | `/add-plugin forbxpg/grillspec` | менеджер плагинов Cursor |
| Antigravity | `agy plugin install https://github.com/forbxpg/grillspec` | повторить установку |
| GigaCode | `gigacode extensions link /path/to/grillspec` (см. [GigaCode](#gigacode)) | заменить содержимое папки |

Codex запускает хуки плагина только после того, как вы доверите им в `/hooks`. До этого
роутер всё равно подгружается по описанию скилла — пропадает только строка статуса.

## Без npx и uv

Ни одна установка ниже не требует npx, npm или uv. Чтобы получить grillspec на машине, где
есть только Python и git (или нет и их), выберите любой способ и оставьте папку на месте:

```bash
git clone https://github.com/forbxpg/grillspec
# или: скачайте source zip релиза с https://github.com/forbxpg/grillspec/releases и распакуйте
# или из зеркала PyPI (исходный дистрибутив содержит весь плагин):
python -m pip download grillspec --no-deps --no-binary :all: && tar -xzf grillspec-*.tar.gz
```

CLI запускается из этой папки её лаунчером, который сам находит Python 3.11+:
`sh scripts/grillspec <command>` на Linux и macOS, `scripts\grillspec.cmd <command>` на
Windows. Или поставьте его командой: `python -m pip install grillspec`, затем
`grillspec <command>`.

## GigaCode

grillspec — нативное расширение GigaCode (`gigacode-extension.json`). GigaCode ставит
расширения только из локальной папки, и для этого нужен лишь он сам:

```bash
gigacode extensions link /path/to/grillspec     # ответьте Y
```

- После этого каждая сессия загружает роутер и строку о том, как запускать CLI grillspec
  из этой папки; 18 скиллов появляются в `/skills`.
- Используйте `link`, а не `install`: `install` видит в папке `.claude-plugin/`, ставит её
  как плагин Claude и теряет и роутер, и ворота.
- Воротам нужны хуки GigaCode, а они по умолчанию выключены. Включите их в
  `~/.gigacode/settings.json`:

  ```json
  { "hooksConfig": { "enabled": true } }
  ```

  (или запускайте GigaCode с `--experimental-hooks`). Без хуков воротами служат только
  скиллы.
- Обновление: замените содержимое папки (`git pull` или распакуйте новый релиз на её
  место); корпоративный режим GigaCode отключает `extensions update`. Удаление:
  `gigacode extensions uninstall grillspec`.

Проверено на сборке GigaCode 0.13.1: `link` загружает оба контекстных файла и все 18
скиллов. Живая сессия, для которой нужна лицензия GigaCode, ещё не запускалась.

## Без системы плагинов

Запасной установщик копирует скиллы в каталог скиллов агента и записывает каждый
созданный файл:

```bash
grillspec install --harness gigacode                 # проект: .gigacode/skills
grillspec install --harness codex --copy --scope user  # пользователь: ~/.agents/skills
grillspec install --harness gigacode --dry-run       # показать записи, ничего не менять
```

(`grillspec` здесь — любой из способов выше: лаунчер, `pip install` или `uvx`.)
Для агентов с плагинами `install` печатает нативную команду, если не передан `--copy`.
Для GigaCode он ещё добавляет одну строку импорта в `GIGACODE.md`, чтобы роутер
загружался в каждой сессии; лучше ставьте расширение: проектные скиллы GigaCode читает,
только если запущен в корне проекта.

## Удаление

```bash
grillspec uninstall --harness gigacode
```

`uninstall` удаляет ровно те файлы и строку импорта, которые `install` записал в
`.grillspec/install-receipt.json` (или в пользовательскую квитанцию рядом с
пользовательским конфигом). Ваши правки в `GIGACODE.md` остаются.

## Настройка проекта

Попросите агента «set up grillspec in this repo». Скилл `grillspec-init` порекомендует бэкенд
спеков, покажет каждое изменение ваших файлов и запишет их только после вашего «да».
То же из терминала:

```bash
grillspec detect
grillspec init --backend openspec --dry-run
grillspec init --backend openspec
```
