# Pikafish Terminal

Play Xiangqi (Chinese Chess) in your terminal against the Pikafish AI engine.

## Install

```bash
pip install pikafish-terminal
```

## Play

```bash
pikafish
```

## Controls

- Enter moves like `1013` (from position 1,0 to 1,3)
- Type `quit` to exit
- Use `--difficulty 1-6` for different AI levels

## Examples

```bash
pikafish --difficulty 5    # Expert level
pikafish --log-level DEBUG # Debug mode
pikafish --info            # Show downloaded files
```

That's it! The AI engine downloads automatically on first run.