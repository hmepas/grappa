#!/bin/bash

VER=$1
if [ -z "$VER" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

# 1. Поднять версию в pyproject.toml (version = "0.1.4"), закоммитить
git commit -am "release v$VER"

# 2. Тег и пуш (тег обязательно запушить — из него собирается tarball для brew)
git tag v$VER
git push origin main --tags

# 3. Обновить brew-формулу (скрипт сам скачает tarball тега и пропишет sha256)
cd ~/projects/formulae
scripts/update-formula.sh $VER
git commit -am "grappa v$VER" && git push
