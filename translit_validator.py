#!/usr/bin/env python3
"""
Массовый транслитератор + SMTP валидатор email.
Поддержка русского и украинского языков.
Остановка проверки после первого валидного аккаунта.
"""
import smtplib
import subprocess
import platform
import socket
import time
import sys
import re
from itertools import product

DOMAIN = "@kifk.ukr.education"
TIMEOUT = 10
FROM_EMAIL = "check@gmail.com"

TRANSLIT_MAP = {
    'а': ['a'], 'б': ['b'], 'в': ['v', 'w'], 'г': ['g', 'h'], 'д': ['d'],
    'е': ['e', 'ye', 'ie'], 'ё': ['yo', 'e', 'io', 'jo'], 'ж': ['zh', 'j'],
    'з': ['z'], 'и': ['i', 'y'], 'й': ['y', 'i', 'j'], 'к': ['k', 'c'],
    'л': ['l'], 'м': ['m'], 'н': ['n'], 'о': ['o'], 'п': ['p'], 'р': ['r'],
    'с': ['s'], 'т': ['t'], 'у': ['u', 'ou'], 'ф': ['f', 'ph'],
    'х': ['kh', 'h', 'x'], 'ц': ['ts', 'c', 'tz'], 'ч': ['ch'], 'ш': ['sh'],
    'щ': ['shch', 'sch', 'shh'], 'ъ': ['', 'ie'], 'ы': ['y', 'i'],
    'ь': ['', "'"], 'э': ['e', 'eh'], 'ю': ['yu', 'iu', 'ju'],
    'я': ['ya', 'ia', 'ja'],
    # Украинские буквы
    'ґ': ['g'], 'є': ['ye', 'ie', 'e'], 'і': ['i'], 'ї': ['yi', 'i', 'ji']
}

def get_variants(cyrillic_word):
    cyrillic_word = cyrillic_word.lower()
    options_per_char = []
    for ch in cyrillic_word:
        if ch in TRANSLIT_MAP:
            options_per_char.append(TRANSLIT_MAP[ch])
        else:
            options_per_char.append([ch])
    variants = [''.join(combo) for combo in product(*options_per_char)]
    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique

def get_mx_host(domain):
    """Get MX host using nslookup (Windows) or host (Linux/Mac)."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["nslookup", "-type=mx", domain],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout
            matches = re.findall(r'mail exchanger\s*=\s*(\d+)\s+(.+)', output, re.IGNORECASE)
            if not matches:
                matches = re.findall(r'MX preference\s*=\s*(\d+).*?mail exchanger\s*=\s*(.+)', output, re.IGNORECASE)
            if matches:
                sorted_mx = sorted(matches, key=lambda x: int(x[0]))
                return sorted_mx[0][1].strip().rstrip(".")
        else:
            result = subprocess.run(
                ["host", "-t", "MX", domain],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout
            matches = re.findall(r'mail is handled by\s+(\d+)\s+(.+)', output)
            if matches:
                sorted_mx = sorted(matches, key=lambda x: int(x[0]))
                return sorted_mx[0][1].strip().rstrip(".")
    except Exception:
        pass
    return None

def check_email_smtp(mx_host, email):
    """Returns True if SMTP server accepts RCPT TO (code 250)."""
    try:
        with smtplib.SMTP(mx_host, 25, timeout=TIMEOUT) as smtp:
            smtp.helo("gmail.com")
            smtp.mail(FROM_EMAIL)
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception:
        return False

def test_port25(mx_host):
    """Quick check if port 25 is reachable."""
    try:
        s = socket.create_connection((mx_host, 25), timeout=5)
        s.close()
        return True
    except Exception:
        return False

def main():
    print("=" * 55)
    print("  Массовый транслитератор + валидатор email")
    print("  Домен: " + DOMAIN)
    print("  Поддержка: RU + UK | Стоп после 1-го валидного")
    print("=" * 55)
    print()
    print("Введите ФИ через запятую. Пример:")
    print("  Иванов Иван, Шевченко Тарас, Коваленко Оксана")
    print()
    print("Для выхода: 'q'\n")

    while True:
        try:
            raw = input("Ввод: ").strip()
        except EOFError:
            break
            
        if raw.lower() in ('q', 'exit', 'quit'):
            break
        if not raw:
            continue

        # Parse comma-separated names
        entries = [e.strip() for e in raw.split(",") if e.strip()]
        people = []
        for entry in entries:
            parts = entry.split()
            if len(parts) < 2:
                print(f"  Пропущено (нет имени): '{entry}'")
                continue
            people.append((parts[0], parts[1], entry))

        if not people:
            print("Ошибка: введите хотя бы одно 'Фамилия Имя'.\n")
            continue

        # Get MX server
        domain = DOMAIN.lstrip("@")
        print(f"\nИщу MX-сервер для {domain}...")
        mx_host = get_mx_host(domain)
        if not mx_host:
            print(f"Ошибка: не удалось найти MX для {domain}.\n")
            continue
        print(f"MX сервер: {mx_host}")

        # Test port 25
        port_ok = test_port25(mx_host)
        if not port_ok:
            print("\n*** ВНИМАНИЕ: Порт 25 заблокирован в вашей сети! ***")
            print("SMTP-проверка не будет работать.")
            print("Варианты решения:")
            print("  1. Подключитесь к мобильному интернету")
            print("  2. Отключите VPN/антивирус")
            print("  3. Используйте онлайн: https://verifalia.com/validate-email")
            print("\nГенерирую все варианты без SMTP-проверки...\n")

        # Process each person
        all_valid = {}
        all_invalid = {}
        all_emails_flat = []

        for surname, name, original in people:
            surname_variants = get_variants(surname)
            name_variants = get_variants(name)
            results = []
            for sv in surname_variants:
                for nv in name_variants:
                    combined = sv + nv
                    if combined not in results:
                        results.append(combined)
            emails = [r + DOMAIN for r in results]
            total = len(emails)
            print(f"\n--- {original} ({total} вариантов) ---")

            if port_ok:
                valid = []
                invalid = []
                for i, email in enumerate(emails, 1):
                    sys.stdout.write(f"\r  [{i}/{total}] {email}...")
                    sys.stdout.flush()
                    if check_email_smtp(mx_host, email):
                        valid.append(email)
                        sys.stdout.write("\r" + " " * 80 + "\r")
                        sys.stdout.flush()
                        print(f"  ✅ Валидный найден: {email} (остальные пропущены)")
                        break  # ⏹️ Останавливаем проверку для этого человека
                    else:
                        invalid.append(email)
                    if i < total:
                        time.sleep(0.2)
                sys.stdout.write("\r" + " " * 80 + "\r")
                sys.stdout.flush()

                if valid:
                    print(f"  ВАЛИДНЫХ: {len(valid)}")
                    for em in valid:
                        print(f"    + {em}")
                else:
                    print(f"  Валидных: 0")
                all_valid[original] = valid
                all_invalid[original] = invalid
            else:
                # Port blocked — just list all variants
                all_emails_flat.extend(emails)
                print(f"  Все варианты: {', '.join(emails)}")

        # === SUMMARY ===
        print("\n" + "=" * 55)
        print("  ИТОГО")
        print("=" * 55)
        if port_ok:
            total_valid = 0
            total_checked = 0
            for original in [p[2] for p in people]:
                v = all_valid.get(original, [])
                inv = all_invalid.get(original, [])
                total_valid += len(v)
                total_checked += len(v) + len(inv)
                status = f"{len(v)} валидных" if v else "нет валидных"
                print(f"  {original}: {status} (проверено {len(v)+len(inv)})")
            print(f"\nВсего проверено: {total_checked}")
            print(f"  Всего валидных:  {total_valid}")

            all_v = []
            for v in all_valid.values():
                all_v.extend(v)
            if all_v:
                print(f"\nВсе валидные аккаунты:")
                for em in all_v:
                    print(f"    -> {em}")
                with open("valid_emails.txt", "w", encoding="utf-8") as f:
                    for em in all_v:
                        f.write(em + "\n")
                print(f"\nСохранено в: valid_emails.txt")
            else:
                print("\nВалидных аккаунтов не найдено.")
        else:
            print(f"  Порт 25 заблокирован — SMTP-проверка невозможна.")
            print(f"  Сгенерировано {len(all_emails_flat)} адресов.")
            with open("all_emails.txt", "w", encoding="utf-8") as f:
                for em in all_emails_flat:
                    f.write(em + "\n")
            with open("all_emails_comma.txt", "w", encoding="utf-8") as f:
                f.write(", ".join(all_emails_flat))
            print(f"\nФайлы для ручной проверки:")
            print(f"    all_emails.txt (по строкам)")
            print(f"    all_emails_comma.txt (через запятую)")
            print(f"\nВставьте в: https://verifalia.com/validate-email")
        print()

if __name__ == "__main__":
    main()
