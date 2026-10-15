"""Start AutoHS. Importing this module does not open the window."""


def main():
    from autohs.app.bootstrap import main as run

    run()


if __name__ == "__main__":
    main()
