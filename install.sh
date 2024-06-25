#!/bin/bash

MOONRAKER_DIR="${HOME}/moonraker"
USER_CONFIG_DIR="${HOME}/printer_data/config"

FS_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

CONFIG_DIR="k_bobine"


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

moonraker_component () {
    if [ ! -d "$MOONRAKER_DIR" ]; then
        echo -e "\e[1;31mFilament settings: Moonraker doesn't exist\e[0m"
        exit 1
    fi
    if [ ! -L "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py" ]; then
        if [ -e "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py" ]; then
            rm "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py"
        fi
        ln -s "${FS_DIR}/moonraker/spoolman_ext.py" "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py"
        echo -e "\e[1;32mspoolman_ext.py linked \e[0m"
    else
        if [ -e "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py" ]; then
            echo -e "\e[1;31mspoolman_ext.py not installed, remove link first \e[0m"
        else
            unlink "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py"
            ln -s "${FS_DIR}/moonraker/spoolman_ext.py" "${MOONRAKER_DIR}/moonraker/components/spoolman_ext.py"
            echo -e "\e[1;32mspoolman_ext.py linked \e[0m"
        fi
    fi
    if ! grep -q "moonraker/components/spoolman_ext.py" "${MOONRAKER_DIR}/.git/info/exclude"; then
        echo "moonraker/components/spoolman_ext.py" >> "${MOONRAKER_DIR}/.git/info/exclude"
    fi


}

klipper_config () {
    echo "Filament settings: include [spoolman_ext] in moonraker.conf"
    if [ ! -d "${USER_CONFIG_DIR}" ]; then
        echo -e "\e[1;31mFilament settings: ${USER_CONFIG_DIR} doesn't exist\e[0m"
        exit 1
    fi

    cp  "${FS_DIR}/config/spoolman_ext.conf" "${USER_CONFIG_DIR}/"
    if ! grep -qF "[include spoolman_ext.conf]" "${USER_CONFIG_DIR}/moonraker.conf"; then
        printf "\n\n[include spoolman_ext.conf]\n" >> "${USER_CONFIG_DIR}/moonraker.conf"
        echo -e "\e[1;32mspoolman_ext.conf installed in moonraker.conf \e[0m"
    else
        echo -e "\e[1;31mspoolman_ext.conf already in moonraker.conf \e[0m"
    fi
    
    echo "Filament settings: install Klipper config files"
    read -p $'\e[35m'"Default folder for Kbobine is ~/printer_data/config. "$'\n'"Write subfolder name or press enter to install '${CONFIG_DIR}' in "$'\n'"${USER_CONFIG_DIR}/<subfolder>/${CONFIG_DIR} ?"$'\e[0m' SUBFOLDER
    if [ ! -d "${USER_CONFIG_DIR}/${SUBFOLDER}" ]; then
        echo -e "\e[1;31mFilament settings: ${USER_CONFIG_DIR}/${SUBFOLDER} doesn't exist\e[0m"
        exit 1
    fi

    if [ ! -d "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}" ]; then
        mkdir "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}"
    fi
    ln -s "${FS_DIR}/config/core" "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}"
    ln -s "${FS_DIR}/config/addons" "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}"
    
    if [ ! -e "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}/config.cfg" ]; then
        cp  "${FS_DIR}/config/config.cfg" "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}/"
    else
        echo -e "\e[1;31mconfig.cfg already installed, update it manually if needed \e[0m"
    fi
        
    if prompt "Do you want to insall Klippain addon ?"; then
        if [ ! -e "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}/klippain.cfg" ]; then
            cp  "${FS_DIR}/config/klippain.cfg" "${USER_CONFIG_DIR}/${SUBFOLDER}/${CONFIG_DIR}/"
            echo -e "[include ./${SUBFOLDER}/${CONFIG_DIR}/config.cfg]" 
        else
            echo -e "\e[1;31mklippain.cfg already installed, update it manually if needed \e[0m"
        fi
    fi
    echo -e "To finalize, insert [include ./${SUBFOLDER}/${CONFIG_DIR}/config.cfg] in your printer.cfg" 
}

moonraker_component
klipper_config

echo -e "\e[1;32mFilament settings: installation successful. \e[0m"
echo "Update your Klipper config and restart Klipper and Moonraker services"
