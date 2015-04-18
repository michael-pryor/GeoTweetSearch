import pickle

class FileAccess(object):
    def __init__(self,fileName,read):
        self.is_read = read

        if read:
            mode = 'rb'
        else:
            mode = 'ab'

        self.file = open(fileName, mode)

    def add(self,object):
        if self.is_read:
            raise TypeError('Usage incorrect, file is readable, not writeable')

        pickle.dump(object,self.file,pickle.HIGHEST_PROTOCOL)
        self.file.flush()

    def __iter__(self):
        if not self.is_read:
            raise TypeError('Usage incorrect, file is writeable, not readable')

        try:
            while True:
                yield pickle.load(self.file)
        except EOFError:
            pass

    def close(self):
        self.file.close()