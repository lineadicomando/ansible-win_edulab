#!/usr/bin/env bash
# Write a Windows installation ISO to a USB stick that boots in UEFI mode,
# Secure Boot included: one FAT32 partition, the files of the ISO, and
# install.wim split into install*.swm pieces below the 4 GiB FAT32 limit.
# Windows Setup reads the split image as it is; autounattend.xml and
# sources/$OEM$ (win_iso role) keep working.
#
# Usage: tools/win_usb.sh [ISO] [DEVICE]
#   Both are asked for when missing. Nothing is written before the device name
#   is typed back. Runs as a normal user: sudo is asked for partitioning and
#   mounting the stick; the ISO is attached read-only through udisksctl.
#
# Needs: lsblk, wipefs, parted, mkfs.vfat (dosfstools), udisksctl, wimlib-imagex,
# rsync. Fedora: sudo dnf install dosfstools parted wimlib-utils rsync
# Debian:       sudo apt install dosfstools parted wimtools rsync udisks2
set -euo pipefail

ISO_DIR=${WIN_USB_ISO_DIR:-/srv/ansible/storage/win_iso}
SPLIT_MIB=3800

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mError: %s\033[0m\n' "$*" >&2; exit 1; }

ask_yes() {
    local reply
    read -r -p "$1 [y/N] " reply
    [[ $reply =~ ^[yYsS]$ ]]
}

# --- cleanup ----------------------------------------------------------------
ISO_LOOP='' ISO_MNT='' USB_MNT='' CHILD=''
cleanup() {
    set +e
    [[ -n $CHILD ]] && kill "$CHILD" 2>/dev/null && wait "$CHILD" 2>/dev/null
    if [[ -n $USB_MNT ]] && mountpoint -q "$USB_MNT"; then
        sudo umount "$USB_MNT"
    fi
    [[ -n $USB_MNT ]] && rmdir "$USB_MNT" 2>/dev/null
    if [[ -n $ISO_LOOP ]]; then
        [[ -n $ISO_MNT ]] && udisksctl unmount -b "$ISO_LOOP" >/dev/null 2>&1
        udisksctl loop-delete -b "$ISO_LOOP" >/dev/null 2>&1
    fi
}
trap cleanup EXIT
trap 'echo; die "interrupted"' INT TERM

# --- tools ------------------------------------------------------------------
missing=()
for tool in lsblk wipefs parted mkfs.vfat udisksctl wimlib-imagex rsync blkid; do
    command -v "$tool" >/dev/null || missing+=("$tool")
done
((${#missing[@]} == 0)) || die "missing tools: ${missing[*]} (see the header of this script)"

# --- ISO --------------------------------------------------------------------
ISO=${1:-}
if [[ -z $ISO ]]; then
    say "Choose the ISO"
    mapfile -t isos < <(find "$ISO_DIR" -maxdepth 1 -type f -iname '*.iso' 2>/dev/null | sort)
    if ((${#isos[@]} == 0)); then
        read -r -e -p "No ISO in $ISO_DIR. Path of the ISO: " ISO
    else
        PS3="ISO number (or a path): "
        select choice in "${isos[@]##*/}"; do
            if [[ -n $choice ]]; then ISO=$ISO_DIR/$choice; break; fi
            if [[ -f $REPLY ]]; then ISO=$REPLY; break; fi
            echo "Not in the list."
        done
    fi
fi
[[ -f $ISO ]] || die "$ISO is not a file"
ISO=$(realpath "$ISO")
ISO_SIZE=$(stat -c %s "$ISO")

# --- USB stick --------------------------------------------------------------
list_usb() {
    lsblk -dnpbo NAME,TRAN,TYPE,SIZE | awk '$2 == "usb" && $3 == "disk" && $4 > 0 { print $1 }'
}
describe() {
    local dev=$1
    printf '%s  %s  %s\n' "$dev" \
        "$(lsblk -dno SIZE "$dev" | xargs)" "$(lsblk -dno VENDOR,MODEL "$dev" | xargs)"
    lsblk -no NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$dev" | tail -n +2 | sed 's/^/    /'
}

DEV=${2:-}
if [[ -z $DEV ]]; then
    say "Choose the USB stick (everything on it will be erased)"
    while :; do
        mapfile -t devs < <(list_usb)
        if ((${#devs[@]} == 0)); then
            read -r -p "No USB stick found. Plug one in and press Enter (Ctrl+C to quit). "
            continue
        fi
        for i in "${!devs[@]}"; do
            printf '%d) ' $((i + 1)); describe "${devs[$i]}"
        done
        read -r -p "Stick number (Enter to refresh the list): " n
        [[ -z $n ]] && continue
        if [[ $n =~ ^[0-9]+$ ]] && ((n >= 1 && n <= ${#devs[@]})); then
            DEV=${devs[$((n - 1))]}; break
        fi
        echo "Not in the list."
    done
fi

# The stick must be a whole USB disk, not hold a system mount, and fit the ISO.
[[ -b $DEV ]] || die "$DEV is not a block device"
[[ $(lsblk -dno TYPE "$DEV") == disk ]] || die "$DEV is a partition: give the whole disk (e.g. /dev/sdb)"
[[ $(lsblk -dno TRAN "$DEV") == usb ]] || die "$DEV is not a USB device"
while read -r mp; do
    [[ -z $mp ]] && continue
    case $mp in
        /run/media/*|/media/*|/mnt/*) ;;
        *) die "$DEV has a partition mounted on $mp: is it really the stick?" ;;
    esac
done < <(lsblk -nlo MOUNTPOINTS "$DEV")
DEV_SIZE=$(lsblk -dnbo SIZE "$DEV")
((DEV_SIZE > ISO_SIZE + 256 * 1024 * 1024)) ||
    die "$DEV ($(numfmt --to=iec "$DEV_SIZE")) is too small for $(numfmt --to=iec "$ISO_SIZE")"

# --- attach the ISO and check it ---------------------------------------------
say "Reading the ISO"
ISO_LOOP=$(udisksctl loop-setup -r -f "$ISO" | grep -o '/dev/loop[0-9]*')
[[ -n $ISO_LOOP ]] || die "udisksctl could not attach $ISO"
for _ in {1..20}; do
    ISO_MNT=$(lsblk -no MOUNTPOINTS "$ISO_LOOP" | head -n1)
    [[ -n $ISO_MNT ]] && break
    # The desktop may mount it by itself; otherwise mount it here.
    udisksctl mount -b "$ISO_LOOP" >/dev/null 2>&1 || sleep 0.5
done
[[ -n $ISO_MNT ]] || die "could not mount $ISO"

[[ -f $ISO_MNT/sources/install.wim ]] ||
    die "the ISO has no sources/install.wim (an install.esd ISO is not handled)"
[[ -f $ISO_MNT/efi/boot/bootx64.efi ]] || die "the ISO has no efi/boot/bootx64.efi: not a UEFI Windows ISO"

ISO_LABEL=$(blkid -o value -s LABEL "$ISO" || true)
USB_LABEL=$(printf '%s' "${ISO_LABEL:-WINSETUP}" | tr -c 'A-Za-z0-9_\n' '_' | tr '[:lower:]' '[:upper:]' | cut -c1-11)

echo "ISO:    $ISO ($(numfmt --to=iec "$ISO_SIZE"), label ${ISO_LABEL:-none})"
wimlib-imagex info "$ISO_MNT/sources/install.wim" |
    awk -F': *' '/^Index/ { i = $2 } /^Display Name/ { print "        edition " i ": " $2 }'
if [[ -f $ISO_MNT/autounattend.xml ]]; then
    warn "        unattended ISO: autounattend.xml holds a password in clear. Keep the stick safe."
fi

# --- confirm ----------------------------------------------------------------
say "Everything on this device will be ERASED:"
describe "$DEV"
echo
read -r -p "Type the device name (${DEV##*/}) to go on: " typed
[[ $typed == "${DEV##*/}" || $typed == "$DEV" ]] || die "not confirmed, nothing written"

sudo -v || die "sudo is needed to partition and mount the stick"

# --- partition and format ---------------------------------------------------
say "Partitioning $DEV: MBR, one FAT32 partition ($USB_LABEL)"
while read -r part mp; do
    [[ -n $mp ]] && { udisksctl unmount -b "$part" >/dev/null 2>&1 || sudo umount "$part"; }
done < <(lsblk -nlpo NAME,MOUNTPOINTS "$DEV" | tail -n +2)
sudo wipefs -a -q "$DEV"
sudo parted -s -a optimal "$DEV" mklabel msdos mkpart primary fat32 1MiB 100% set 1 boot on
sudo udevadm settle
PART=$(lsblk -nlpo NAME,TYPE "$DEV" | awk '$2 == "part" { print $1; exit }')
[[ -b $PART ]] || die "the new partition did not appear on $DEV"
sudo mkfs.vfat -F 32 -n "$USB_LABEL" "$PART" >/dev/null
sudo udevadm settle
# The desktop may mount the fresh partition: take it back.
if [[ -n $(lsblk -no MOUNTPOINTS "$PART") ]]; then
    udisksctl unmount -b "$PART" >/dev/null 2>&1 || sudo umount "$PART"
fi

USB_MNT=$(mktemp -d /tmp/win_usb.XXXXXX)
mount_usb() { sudo mount -o "uid=$(id -u),gid=$(id -g),utf8" "$PART" "$USB_MNT"; }
mount_usb

# --- copy -------------------------------------------------------------------
# rsync and wimlib report what they hand to the page cache, which a slow stick
# drains long after: their counters race ahead, then stall. Progress here counts
# the bytes that actually reached the device (/proc/diskstats), across all steps.
dev_written() { awk -v d="${DEV##*/}" '$3 == d { print $10 * 512 }' /proc/diskstats; }
duration() { printf '%d:%02d' $(($1 / 60)) $(($1 % 60)); }
TOTAL=$(du -sb --apparent-size "$ISO_MNT" | cut -f1)
W0=$(dev_written) T0=$SECONDS

show_progress() {
    local done_=${1:-} w=$(($(dev_written) - W0)) t=$((SECONDS - T0)) pct eta=''
    pct=$((w * 100 / TOTAL))
    if [[ -z $done_ ]]; then
        ((pct > 99)) && pct=99
        if ((t >= 10 && w > 0)); then
            eta=", about $(duration $(( (TOTAL > w ? TOTAL - w : 0) * t / w ))) left"
        fi
    fi
    printf '\r\033[K  %s of %s on the stick (%d%%), %s/s, %s elapsed%s' \
        "$(numfmt --to=iec "$w")" "$(numfmt --to=iec "$TOTAL")" "$pct" \
        "$(numfmt --to=iec $((t > 0 ? w / t : 0)))" "$(duration "$t")" "$eta"
}

# Run a command quietly in the background, showing the progress until it ends.
with_progress() {
    local log rc=0
    log=$(mktemp)
    "$@" >"$log" 2>&1 &
    CHILD=$!
    while kill -0 "$CHILD" 2>/dev/null; do
        show_progress; sleep 2
    done
    wait "$CHILD" || rc=$?
    CHILD=''
    if ((rc != 0)); then
        echo; cat "$log" >&2; rm -f "$log"
        die "$1 failed (exit $rc)"
    fi
    rm -f "$log"
}

say "Copying the files of the ISO (without install.wim)"
with_progress rsync -r --exclude=/sources/install.wim "$ISO_MNT"/ "$USB_MNT"/
echo

say "Splitting install.wim into pieces of $SPLIT_MIB MiB on the stick (the longest step)"
with_progress wimlib-imagex split "$ISO_MNT/sources/install.wim" "$USB_MNT/sources/install.swm" "$SPLIT_MIB"
echo

say "Flushing what is still in memory to the stick"
with_progress sync -f "$USB_MNT"
show_progress final; echo

if ask_yes "Verify the split image now? It reads it all back from the stick, a few minutes more."; then
    # Remount first: otherwise the reads come from the page cache, not the stick.
    sudo umount "$USB_MNT"; mount_usb
    wimlib-imagex verify "$USB_MNT/sources/install.swm" --ref="$USB_MNT/sources/install*.swm"
fi

ls -lh "$USB_MNT/sources/"install*.swm

# --- finish -----------------------------------------------------------------
sudo umount "$USB_MNT"; rmdir "$USB_MNT"; USB_MNT=''
say "Done: $DEV boots Windows Setup in UEFI mode (Secure Boot on or off)."
if ask_yes "Power off the stick so it can be unplugged?"; then
    udisksctl power-off -b "$DEV" && echo "You can unplug it."
fi
