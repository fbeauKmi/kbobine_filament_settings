#!/bin/bash

MOONRAKER_DIR="${HOME}/moonraker"
KLIPPY_DIR="${HOME}/klipper/klippy/"
USER_CONFIG_DIR="${HOME}/printer_data/config"

FS_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

CONFIG_DIR="kbobine"

usage() {
  cat << EOF
Usage: $0 [-o|--option]

Kbobine installer

Optional args:
  -m, --minimal              Install 'spoolman_ext.py' only.
  -f, --force                Force Moonraker and Klipper component installation.
  -h, --help                 Display this help message and exit.
EOF
}

# Define a function to prompt the user with a yes/no question and return their answer
prompt () {
    while true; do
        read -p $'\e[35m'"$* [Y/n]: "$'\e[0m' yn
        case $yn in
            [Yy]*) return 0  ;;
            "")    return 0  ;;  # Return 0 on Enter key press (Y as default)
            [Nn]*) return 1  ;;
        esac
    done
}

moonraker_component (component) {
    if [ ! -d "$MOONRAKER_DIR" ]; then
        echo -e "\e[1;31mFatal Error : Moonraker is not installed\e[0m"
        exit 1
    fi
    if [ ! -L "${MOONRAKER_DIR}/moonraker/components/$component.py" ]; then
        if [ -e "${MOONRAKER_DIR}/moonraker/components/$component.py" ]; then
            rm "${MOONRAKER_DIR}/moonraker/components/$component.py"
        fi
        ln -s "${FS_DIR}/moonraker/$component.py" "${MOONRAKER_DIR}/moonraker/components/$component.py"
        echo -e "\e[1;32m$component.py linked \e[0m"
    else
        if ( ! $FORCE ) && [ -e "${MOONRAKER_DIR}/moonraker/components/$component.py" ]; then
            echo -e "\e[1;31m$component.py already installed, use -f option to install it anyway \e[0m"
            return 0
        else
            unlink "${MOONRAKER_DIR}/moonraker/components/$component.py"
            ln -s "${FS_DIR}/moonraker/$component.py" "${MOONRAKER_DIR}/moonraker/components/$component.py"
            echo -e "\e[1;32m$component.py linked \e[0m"
        fi
    fi
    if ! grep -q "moonraker/components/$component.py" "${MOONRAKER_DIR}/.git/info/exclude"; then
        echo "moonraker/components/$component.py" >> "${MOONRAKER_DIR}/.git/info/exclude"
    fi
}

moonraker_config (component) {
    echo "Install include [$component] in moonraker.conf"
    if [ ! -d "${USER_CONFIG_DIR}" ]; then
        echo -e "\e[1;31mFatal Error : ${USER_CONFIG_DIR} doesn't exist\e[0m"
        exit 1
    fi

    cp  "${FS_DIR}/moonraker/$component.conf" "${USER_CONFIG_DIR}/"
    if ! grep -qF "[include $component.conf]" "${USER_CONFIG_DIR}/moonraker.conf"; then
        printf "\n\n[include $component.conf]\n" >> "${USER_CONFIG_DIR}/moonraker.conf"
        echo -e "\e[1;32m$component.conf installed in moonraker.conf \e[0m"
    else
        echo -e "\e[1;31m$component.conf already in moonraker.conf \e[0m"
    fi
}

klipper_config () {
    
    echo "Filament settings: install Klipper config files"
    read -p $'\e[35m'"Default folder for Kbobine is ~/printer_data/config. "$'\n'"Write subfolder name or press enter to install '${CONFIG_DIR}' in "$'\n'"${USER_CONFIG_DIR}/<subfolder>/${CONFIG_DIR} ?"$'\e[0m' SUBFOLDER
    if [ ! -d "${USER_CONFIG_DIR}/${SUBFOLDER}" ]; then
        echo -e "\e[1;31mFatal Error : ${USER_CONFIG_DIR}/${SUBFOLDER} doesn't exist\e[0m"
        exit 1
    fi

    if [ ! -d "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}" ]; then
        mkdir "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}"
    fi
    ln -s "${FS_DIR}/klipper_config/addons" "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}"
    
    if [ ! -e "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}/config.cfg" ]; then
        cp  "${FS_DIR}/klipper_config/config.cfg" "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}/"
    else
        echo -e "\e[1;31mconfig.cfg already installed, update it manually if needed \e[0m"
    fi

    echo -e "To finalize installation, edit and insert [include ./${SUBFOLDER}/${CONFIG_DIR}/config.cfg] in your printer.cfg" 
}

function klipper_component(){
    echo "Installing klipper modules" 
    PLUGINS_FOLDER="${KLIPPY_DIR}/extras"
    # check if the plugins folder exists, if so, use it instead of extras
    [[ -d "${KLIPPY_DIR}/plugins" ]] && PLUGINS_FOLDER="${KLIPPY_DIR}/plugins"
    find "${FS_DIR}/klipper/klippy/plugins" -name "*.py" -type f | while read file; do
        filename=$(basename "$file")
        ln -s "$file" "${PLUGINS_FOLDER}"
        echo "$filename installed in ${PLUGINS_FOLDER}"
    done;
}

HELP=false; MINIMAL=false; FORCE=false;

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--minimal)    MINIMAL=true;;
    -f|--force)     FORCE=true;;
    -*|--*)       HELP=true ;;
    *)
     esac
  shift
done

# Call usage function if --help or -h is specified
if [[ $HELP == true ]]; then
  usage
  exit 0
fi

echo "   +-------------------------+
   |                         |
   |    KBobine Installer    |
   |                         |
   +-------------------------+
"
if MINIMAL; then
    echo -e "\e[1;33mMinimal installation: only Moonraker component will be installed. \e[0m"
    moonraker_component spoolman_ext
    moonraker_config spoolman_ext
    echo -e "\e[1;32mKbobine Moonraker component: installation successful. \e[0m"
else
    echo -e "\e[1;33mFull installation: Moonraker component and Klipper config will be installed. \e[0m"
    moonraker_component kbobine
    moonraker_config kbobine
    echo -e "\e[1;32mKbobine Moonraker component: installation successful. \e[0m"
    klipper_config
    echo -e "\e[1;32mFilament settings: installation successful. \e[0m"
    klipper_component
fi


echo "
Thank you for installing Kbobine !
Setup your Klipper/Moonraker config and restart Klipper/Moonraker services.
See documentation for more informations."
