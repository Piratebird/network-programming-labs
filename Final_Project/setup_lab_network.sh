#!/usr/bin/env bash

# ==============================================================================
# Network Lab Setup Script
# Manages virbr0 and static routes for the VyOS router.
# Usage: ./setup_lab_network.sh [command]
# ==============================================================================

set -euo pipefail

# --- Constants ---------------------------------------------------------------
readonly SCRIPT_NAME="$(basename "$0")"
readonly ROUTER_IP="192.168.122.147"
readonly VIRBR_NAME="virbr0"
readonly LAN1="192.168.1.0/24"
readonly LAN2="192.168.2.0/24"
readonly DEFAULT_NET="default"

# --- Colors ------------------------------------------------------------------
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# --- Utility Functions -------------------------------------------------------

info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
header(){ printf "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"; }
subheader(){ printf "${CYAN}--- %s ---${NC}\n" "$*"; }

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "Please run this script with sudo or as root."
        exit 1
    fi
}

confirm() {
    local prompt="$1"
    local reply
    printf "${YELLOW}%s [y/N]: ${NC}" "$prompt"
    read -r reply
    case "$reply" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

# --- Core Functions ----------------------------------------------------------

ensure_libvirtd() {
    info "Starting libvirtd service..."
    systemctl start libvirtd
    systemctl enable libvirtd 2>/dev/null || true
}

virbr_exists() {
    ip link show "$VIRBR_NAME" >/dev/null 2>&1
}

add_virbr() {
    header
    subheader "Adding virtual bridge ($VIRBR_NAME)"

    if virbr_exists; then
        info "$VIRBR_NAME is already up."
        return 0
    fi

    ensure_libvirtd

    if virsh net-start "$DEFAULT_NET" >/dev/null 2>&1; then
        info "Network '$DEFAULT_NET' started."
    else
        warn "Network '$DEFAULT_NET' was already active."
    fi
    virsh net-autostart "$DEFAULT_NET" >/dev/null 2>&1 || true

    sleep 2

    if virbr_exists; then
        info "$VIRBR_NAME is now up."
    else
        error "$VIRBR_NAME did not come up. Check libvirt installation."
        exit 1
    fi
}

remove_virbr() {
    header
    subheader "Removing virtual bridge ($VIRBR_NAME)"

    if ! virbr_exists; then
        info "$VIRBR_NAME is not present — nothing to remove."
        return 0
    fi

    if ! confirm "This will destroy the '$DEFAULT_NET' network. Continue?"; then
        info "Cancelled."
        return 0
    fi

    # Remove routes that depend on virbr0 first
    remove_routes

    if virsh net-destroy "$DEFAULT_NET" >/dev/null 2>&1; then
        info "Network '$DEFAULT_NET' destroyed."
    else
        warn "Could not destroy '$DEFAULT_NET' (it may not exist)."
    fi

    sleep 1

    if ! virbr_exists; then
        info "$VIRBR_NAME has been removed."
    else
        warn "$VIRBR_NAME is still present. You may need to stop VMs using it first."
    fi
}

add_routes() {
    header
    subheader "Adding static routes via VyOS ($ROUTER_IP)"

    if ! virbr_exists; then
        error "$VIRBR_NAME is not up. Run 'add-virbr' first."
        return 1
    fi

    ip route replace "$LAN1" via "$ROUTER_IP" dev "$VIRBR_NAME"
    ip route replace "$LAN2" via "$ROUTER_IP" dev "$VIRBR_NAME"

    info "Routes added:"
    printf "  %-18s via %-15s dev %s\n" "$LAN1" "$ROUTER_IP" "$VIRBR_NAME"
    printf "  %-18s via %-15s dev %s\n" "$LAN2" "$ROUTER_IP" "$VIRBR_NAME"
}

remove_routes() {
    header
    subheader "Removing static routes"

    local removed=false
    for net in "$LAN1" "$LAN2"; do
        if ip route del "$net" via "$ROUTER_IP" dev "$VIRBR_NAME" 2>/dev/null; then
            info "Removed route for $net"
            removed=true
        fi
    done

    if ! $removed; then
        info "No matching routes found to remove."
    fi
}

show_status() {
    header
    subheader "Virtual Bridge Status"
    if virbr_exists; then
        printf "${GREEN}✔${NC} %s is up\n" "$VIRBR_NAME"
        ip -br addr show "$VIRBR_NAME" 2>/dev/null | awk '{printf "   IP: %s %s\n", $3, $4}'
    else
        printf "${RED}✘${NC} %s is not present\n" "$VIRBR_NAME"
    fi

    echo ""
    subheader "Static Routes via $ROUTER_IP"
    local routes
    routes=$(ip route | grep -E "^(${LAN1}|${LAN2})") || true
    if [ -n "$routes" ]; then
        printf "${GREEN}✔${NC} Routes found:\n"
        echo "$routes" | sed 's/^/   /'
    else
        printf "${RED}✘${NC} No routes to %s / %s via %s\n" "$LAN1" "$LAN2" "$ROUTER_IP"
    fi

    echo ""
    subheader "Libvirt Network State"
    virsh net-list --all 2>/dev/null | grep -E "^ (default|Name)" || echo "   (unable to query libvirt)"

    echo ""
    subheader "Routing Table (virbr0 related)"
    ip route show dev "$VIRBR_NAME" 2>/dev/null | sed 's/^/   /' || echo "   (none)"
}

all_up() {
    add_virbr
    add_routes
    echo ""
    info "Everything is set up!"
}

all_down() {
    remove_routes
    remove_virbr
    echo ""
    info "All cleaned up."
}

# --- Interactive Menu --------------------------------------------------------

interactive_menu() {
    local choice
    while true; do
        clear 2>/dev/null || true
        header
        printf "${BOLD}  Virtual Network Lab Manager${NC}\n"
        header
        echo ""
        echo "  1)  Setup everything     (virbr0 + routes)"
        echo "  2)  Teardown everything   (routes + virbr0)"
        echo "  3)  Add virbr0 only"
        echo "  4)  Remove virbr0 only"
        echo "  5)  Add static routes only"
        echo "  6)  Remove static routes only"
        echo "  7)  Show status"
        echo "  8)  Exit"
        echo ""
        printf "${CYAN}Choice [1-8]: ${NC}"
        read -r choice
        echo ""

        case "$choice" in
            1) all_up ;;
            2) all_down ;;
            3) add_virbr ;;
            4) remove_virbr ;;
            5) add_routes ;;
            6) remove_routes ;;
            7) show_status ;;
            8) info "Exiting."; exit 0 ;;
            *) warn "Invalid choice. Please select 1-8." ;;
        esac

        echo ""
        printf "${YELLOW}Press Enter to return to the menu...${NC}"
        read -r
    done
}

# --- CLI Entry Point ---------------------------------------------------------

show_usage() {
    cat <<EOF
Usage: $SCRIPT_NAME [command]

Commands:
  all-up         Start virbr0 and add static routes (default)
  all-down       Remove static routes and destroy virbr0
  add-virbr      Start the libvirt 'default' network (creates virbr0)
  remove-virbr   Destroy the libvirt 'default' network (removes virbr0)
  add-routes     Add static routes via VyOS ($ROUTER_IP)
  remove-routes  Remove static routes via VyOS ($ROUTER_IP)
  status         Show current network state
  menu           Launch interactive menu
  help           Show this help message

EOF
}

main() {
    # Handle help/usage first so it works without root
    case "${1:-}" in
        help|--help|-h)
            show_usage
            exit 0
            ;;
    esac

    check_root

    case "${1:-menu}" in
        all-up|up)          all_up ;;
        all-down|down)      all_down ;;
        add-virbr)          add_virbr ;;
        remove-virbr|rm-virbr) remove_virbr ;;
        add-routes)         add_routes ;;
        remove-routes|rm-routes) remove_routes ;;
        status|show)        show_status ;;
        menu|interactive)   interactive_menu ;;
        *)
            error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
