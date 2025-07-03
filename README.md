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
- Type `h` for move hints
- Type `s` to toggle score display
- Type `quit` to exit

## Examples

```bash
pikafish --difficulty 3     # Medium level (1-5)
pikafish --depth 10         # Custom depth
pikafish --time 2.0         # Custom time limit
pikafish --config-list      # Show all settings
```

## Configuration

Settings are stored in `config.yaml` (auto-created). Edit this file to customize difficulties, hints, and display options.

That's it! The AI engine downloads automatically on first run.