# sets up configuration file. Step by step or via command line arguments
import os
import argparse
import colorama

from config import SiteConfig, load_config

title_color = colorama.Fore.CYAN
subtitle_color = colorama.Fore.YELLOW
text_color = colorama.Fore.RESET
error_color = colorama.Fore.RED


def get_parser():
    parser = argparse.ArgumentParser(description="Setup the blog configuration")
    parser.add_argument("-y", "--yes", action="store_true", help="Run setup with default values (no prompts)")
    parser.add_argument("--title", help="Site title")
    parser.add_argument("--description", help="Site description")
    parser.add_argument("--author", help="Author name")
    parser.add_argument("--legal-email", help="Legal email for impressum")
    parser.add_argument("--legal-name", help="Legal name for impressum")
    parser.add_argument("--legal-address", help="Legal address for impressum")
    parser.add_argument("--legal-phone", help="Legal phone number for impressum")
    parser.add_argument("--theme", help="Theme name (e.g., 'light', 'dark')")
    parser.add_argument("--admin-user", help="Admin username")
    parser.add_argument("--admin-pass", help="Admin password")
    return parser

def init_auto_config(args):
    config = SiteConfig.create_default()
    
    # Override defaults with provided arguments
    if args.title:
        config.site_name = args.title
    if args.description:
        config.site_description = args.description
    if args.author:
        config.author_name = args.author
    if args.legal_email:
        config.legal_email = args.legal_email
    if args.legal_name:
        config.legal_name = args.legal_name
    if args.legal_address:
        config.legal_address = args.legal_address
    if args.legal_phone:
        config.legal_phone = args.legal_phone
    if args.admin_user:
        config.admin_user = args.admin_user
    if args.admin_pass:
        config.admin_pass = args.admin_pass
    
    return config
  

def get_input(prompt, default=None, check_func=None, requirements_info=None):
    while True:
        print(prompt, end="")
        if default:
            print(f" [{default}]", end="")
        print(": ", end="")
        value = input()
        if not value and default is not None:
            value = default
        if check_func:
            if not check_func(value):
                if requirements_info:
                    print(colorama.Fore.RED + f"Input does not meet requirements: {requirements_info}" + colorama.Fore.RESET)
                else:                    
                    print(colorama.Fore.RED + "Invalid input. Please try again." + colorama.Fore.RESET)
                continue
        return value
  

def init_manual_config(args):
    config = SiteConfig.create_default()
    
    
    
    print(title_color + "Let's set up your blog configuration step by step. Press Enter to keep the default value shown in brackets." + colorama.Fore.RESET)
    
    if not all([args.admin_user, args.admin_pass]):
        print(subtitle_color + "Admin Credentials" + colorama.Fore.RESET)
    config.admin_user = args.admin_user or get_input(f"{text_color}Admin Username", check_func=lambda x: len(x) >= 3, requirements_info="At least 3 characters")
    config.admin_pass = args.admin_pass or get_input(f"{text_color}Admin Password", check_func=lambda x: len(x) >= 8, requirements_info="At least 8 characters")
    
    if not all([args.title, args.description, args.author]):
        print(subtitle_color + "Site Information" + colorama.Fore.RESET)
    config.site_name =  args.title or get_input(f"{text_color}Site Title", default=config.site_name)
    config.site_description = args.description or get_input(f"{text_color}Site Description", default=config.site_description)
    config.author_name = args.author or get_input(f"{text_color}Author Name", default=config.author_name)
    
    if not all([args.legal_email, args.legal_name, args.legal_address, args.legal_phone]):
        print(subtitle_color + "Legal Information (Impressum)" + colorama.Fore.RESET)
    config.legal_name = args.legal_name or get_input(f"{text_color}Legal Name", default=config.legal_name)
    config.legal_email = args.legal_email or get_input(f"{text_color}Legal Email", default=config.legal_email)
    config.legal_address = args.legal_address or get_input(f"{text_color}Legal Address", default=config.legal_address)
    config.legal_phone = args.legal_phone or get_input(f"{text_color}Legal Phone", default=config.legal_phone)

    
    return config

def credentials_check(name, password):
    if name and len(name) < 3:
        return False
    if password and len(password) < 8:
        return False
    return True

def main():
    colorama.init(autoreset=True)
    
    parser = get_parser()
    
    args = parser.parse_args()
    
    if not credentials_check(args.admin_user, args.admin_pass):
        print(colorama.Fore.RED + "Error: Admin username must be at least 3 characters and password must be at least 8 characters." + colorama.Fore.RESET)
        return
    
    config = None
    
    # first, check if -y was used. If so, admin-user and admin-pass must be provided, otherwise we can't run with defaults
    if args.yes:
        if not args.admin_user or not args.admin_pass:
            print(colorama.Fore.RED + "Error: When using -y/--yes, you must provide --admin-user and --admin-pass" + colorama.Fore.RESET)
            return
        
        config = init_auto_config(args)
    else:
        config = init_manual_config(args)
        
    # Save the config to file
    config.save_to_file()
    print(colorama.Fore.GREEN + "Configuration saved.")
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSetup interrupted by user. Exiting.")
    except Exception as e:
        print(colorama.Fore.RED + f"An error occurred during setup: {e}" + colorama.Fore.RESET)