#!/usr/bin/env bash
set -euo pipefail

# KDE/Wayland deliberately lets the compositor decide whether a client's
# stays-on-top hint is honored. This exact-title KWin rule affects only
# Timee's mini timer and places it in KWin's overlay layer.
case ";${XDG_CURRENT_DESKTOP:-};${XDG_SESSION_DESKTOP:-};" in
    *KDE*|*kde*) ;;
    *)
        printf '%s\n' 'KDE Plasma algılanmadı; KWin mini pencere kuralı atlandı.'
        exit 0
        ;;
esac

if ! command -v kwriteconfig6 >/dev/null 2>&1 || ! command -v kreadconfig6 >/dev/null 2>&1; then
    printf '%s\n' 'KWin kuralı için kwriteconfig6 ve kreadconfig6 gerekli.' >&2
    exit 1
fi

timee_rule_id="timee-mini-overlay"
legacy_rule_id="mola-mini-overlay"
existing_order="$(kreadconfig6 --file kwinrulesrc --group General --key Order --default '')"
# Remove only the keys written by Timee's previous Mola installer.  Leaving an
# orphaned populated group causes KWin to add it back to General/Order when it
# reloads the rules file.
legacy_keys=(
    Description Enabled above aboverule layer layerrule positionrule
    skippager skippagerrule skipswitcher skipswitcherrule
    skiptaskbar skiptaskbarrule title titlematch
)
for key in "${legacy_keys[@]}"; do
    kwriteconfig6 --file kwinrulesrc --group "$legacy_rule_id" --key "$key" --delete ''
done
filtered_order=""
IFS=',' read -r -a rule_ids <<< "$existing_order"
for rule_id in "${rule_ids[@]}"; do
    [[ -z "$rule_id" || "$rule_id" == "$timee_rule_id" || "$rule_id" == "$legacy_rule_id" ]] && continue
    if [[ -z "$filtered_order" ]]; then
        filtered_order="$rule_id"
    else
        filtered_order="${filtered_order},${rule_id}"
    fi
done
new_order="$timee_rule_id"
[[ -n "$filtered_order" ]] && new_order="${new_order},${filtered_order}"

kwriteconfig6 --file kwinrulesrc --group General --key Order "$new_order"
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key Description "Timee mini sayaç · daima üstte"
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key Enabled true
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key title "Timee · Mini sayaç"
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key titlematch 1
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key above true
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key aboverule 2
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key layer overlay
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key layerrule 2
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key positionrule 4
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key skiptaskbar true
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key skiptaskbarrule 2
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key skippager true
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key skippagerrule 2
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key skipswitcher true
kwriteconfig6 --file kwinrulesrc --group "$timee_rule_id" --key skipswitcherrule 2

skip_reconfigure="${TIMEE_SKIP_KWIN_RECONFIGURE:-${MOLA_SKIP_KWIN_RECONFIGURE:-0}}"
if [[ "$skip_reconfigure" != "1" ]] && command -v qdbus-qt6 >/dev/null 2>&1; then
    qdbus-qt6 org.kde.KWin /KWin org.kde.KWin.reconfigure >/dev/null 2>&1 || true
fi

printf '%s\n' 'KWin kuralı kuruldu: Timee mini sayaç diğer pencerelerin üstünde kalacak.'
