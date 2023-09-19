import argparse, os, sys
from . import utils
from .postgres import PostgreSQL
from .mysql import MySQL

def main():
    print(utils.tColors.BOLD + utils.tColors.BLUE + f"""
     _     _ _                 _ _     
    | |__ | (_)_ __         __| | |__  
    | '_ \| | | '_ \ _____ / _` | '_ \ 
    | |_) | | | | | |_____| (_| | |_) |
    |_.__/|_|_|_| |_|      \__,_|_.__/ 
                                                        
    """ + utils.tColors.ENDC)
    parser = argparse.ArgumentParser(
            prog='blindb',
            description='Exploit any blind sql injection to exfiltrate database data',
            epilog='(Currently supports MySQL and Postgres)')

    parser.add_argument('--adapter', required = True)
    parser.add_argument('--dbms', required = True, choices=['postgres', 'mysql'])
    parser.add_argument('--output', required = True, help='A file name where the output will be saved')
    parser.add_argument('--tables-db', required = False, default=None, help='Local db file path. If present the tables data will be extracted and inserted in a sqlite db')

    args = parser.parse_args()

    if not os.path.isfile(args.adapter):
        utils.printError(f'Adapter module "{args.adapter}" not found')
        sys.exit(1)

    adapter = utils.loadModule(args.adapter)

    if not 'isTrue' in dir(adapter) or not callable(getattr(adapter, 'isTrue')):
        utils.printError(f'The loaded module does not define the method isTrue')
        sys.exit(1)

    if args.dbms == 'postgres':
        PostgreSQL(adapter.isTrue, args.output, args.tables_db).run()
    else:
        MySQL(adapter.isTrue, args.output, args.tables_db).run()