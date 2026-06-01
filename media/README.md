# Media Assets Directory

This directory contains all media assets used by the Dugout.ai production system.

## Directory Structure

```
media/
├── audio/
│   ├── walkup/       # Player walk-up music files
│   ├── fallback/     # Default/fallback tracks when player track is missing
│   └── effects/      # Sound effects (crowd cheer, organ riff, etc.)
├── images/
│   ├── headshots/    # Player headshot images
│   ├── team-logos/   # Team logo images (PNG with transparency)
│   └── templates/    # Graphics template background images
└── README.md
```

## Asset Naming Conventions

### Walk-Up Music
- Format: `.mp3` or `.wav`
- Naming: `{player_id}.mp3` (e.g., `player_ashland_17.mp3`)
- Duration: 15-30 seconds recommended
- Fallback track: `fallback/default_walkup.mp3`

### Headshots
- Format: `.png` (with transparency) or `.jpg`
- Naming: `{player_id}.png` (e.g., `player_ashland_17.png`)
- Size: 400x400px minimum, square aspect ratio
- Background: Transparent PNG preferred for overlay use

### Team Logos
- Format: `.png` (with transparency)
- Naming: `{team_id}.png` (e.g., `team_ashland.png`)
- Size: 200x200px minimum

### Graphics Templates
- Format: `.png` or `.svg`
- Naming: `{template_type}_{variant}.png` (e.g., `batter_intro_v1.png`)

## Adding Assets

1. Place files in the appropriate directory following naming conventions
2. Register the asset in the database via the dashboard Media Management panel or seed SQL
3. The system will resolve `asset_id` → file path automatically

## Supported Formats

| Type | Formats | Max Size |
|------|---------|----------|
| Audio | `.mp3`, `.wav`, `.ogg` | 10 MB |
| Image | `.png`, `.jpg`, `.jpeg`, `.svg` | 5 MB |
| Video | `.mp4`, `.webm` | 50 MB |
