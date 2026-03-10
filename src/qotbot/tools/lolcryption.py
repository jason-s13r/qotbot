import math
from fastmcp import FastMCP

lolcryption = FastMCP("Lolcryption")


LOLCRYPT_IN = "aeioubcdfghjklmnpqrstvwxyz"
LOLCRYPT_OUT = "iouaenpqrstvwxyzbcdfghjklm"
KEYBOARD_SHIFT_IN = "1234567890-=qwertyuiopasdfghjkl;'zxcvbnm,./"
KEYBOARD_SHIFT_OUT = "/1234567890-=qwertyuiopasdfghjkl;'zxcvbnm,."

@lolcryption.tool
def tr(text: str, before: str, after: str) -> str:
    """Translate text from one character set to another."""

    return _tr(text, before, after)

@lolcryption.tool
def rot13(text: str) -> str:
    """Rotate text by 13 places."""

    return _tr(text, "abcdefghijklmnopqrstuvwxyz", "nopqrstuvwxyzabcdefghijklm")

@lolcryption.tool
def enlolcrypt(text: str) -> str:
    """Encrypt text using Lolcryption."""

    return _tr(text, LOLCRYPT_IN, LOLCRYPT_OUT)

@lolcryption.tool
def delolcrypt(text: str) -> str:
    """Decrypt text using Lolcryption."""

    return _tr(text, LOLCRYPT_OUT, LOLCRYPT_IN)

@lolcryption.tool
def keyboardShiftLeft(text: str) -> str:
    """Shift keyboard input to the left."""

    return _tr(text, KEYBOARD_SHIFT_IN, KEYBOARD_SHIFT_OUT)

@lolcryption.tool
def keyboardShiftRight(text: str) -> str:
    """Shift keyboard input to the right."""

    return _tr(text, KEYBOARD_SHIFT_OUT, KEYBOARD_SHIFT_IN)

@lolcryption.tool
def theucon_encrypt(text: str) -> str:
    """Encrypt text using Theucon encryption."""

    output = ""
    remaining = text
    while len(remaining) > 0:
        primeIndexed = ""
        nonPrimeIndexed = ""
        for i in range(0, len(remaining)):
            if i == 0 or _is_prime(i):
                primeIndexed = primeIndexed + remaining[i]
            else:
                nonPrimeIndexed = nonPrimeIndexed + remaining[i]
        output = output + primeIndexed
        remaining = nonPrimeIndexed
    return output


@lolcryption.tool
def theucon_decrypt(text: str) -> str:
    """Decrypt text using Theucon encryption."""
    output = _make_empty_list(len(text), "")
    remaining = text
    while len(remaining) > 0:
        primes = [0] + _primes_until(len(remaining))
        currentOutput = _make_empty_list(len(remaining), "")
        current = remaining[0 : len(primes)]
        remaining = remaining[len(primes) :]
        for i in range(0, len(primes)):
            currentOutput[primes[i]] = current[i]
        if len(output) == 0:
            output = currentOutput
        else:
            for i in range(0, len(output)):
                if output[i] == "":
                    output[i] = currentOutput[0]
                    currentOutput = currentOutput[1:]
    return str.join("", output)

def _tr(text: str, before: str, after: str) -> str:
    text = text.translate(str.maketrans(before, after))
    return text.translate(str.maketrans(before.upper(), after.upper()))

def _is_prime(n: int) -> bool:
    if n < 2 or n % 2 == 0 and n > 2:
        return False
    return all(n % i for i in range(3, int(math.sqrt(n)) + 1, 2))

def _primes_until(n: int) -> list[int]:
    primes = []
    for x in range(1, n):
        if _is_prime(x):
            primes.append(x)
    return primes


def _make_empty_list(n: int, sep: str = "") -> list[str]:
    lst = []
    for x in range(0, n):
        lst.append(sep)
    return lst


if __name__ == "__main__":
    lolcryption.run()