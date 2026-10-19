"""Host wordlist paths must map to their read-only path inside the container."""

from core.executor import WORDLIST_MOUNT, container_wordlist


def test_host_path_maps_to_container_mount_by_filename():
    assert container_wordlist("/home/zedx/Downloads/rockyou.txt-main/rockyou.txt") == \
        f"{WORDLIST_MOUNT}/rockyou.txt"


def test_windows_style_path_maps_by_filename_too():
    assert container_wordlist("/mnt/d/TheRecon/users.txt") == f"{WORDLIST_MOUNT}/users.txt"
