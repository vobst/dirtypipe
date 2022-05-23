'''
# TODO 
> add gdb cli functions
lkd_page_address
lkd_page_data
lkd_file_name
lkd_file_path
'''

import gdb as g

'''
@global Task        task    'struct task_struct' of poc process
@global Pipe        pipe    'struct pipe_inode_info' of our pipe
@global PipeBuffer  buf     'struct pipe_buffer' of our pipe
@global File        file    'struct file' of target file
@global AddrSpace   fmap    'struct address_space' representing the
                            target target file in the page cache
@global Page        page    'struct page' holding data in page cache
'''
task = None
pipe = None
buf = None
file = None
fmap = None
page = None


'''
Struct classes
'''
class GenericStruct():
    '''
    Info: Container for a struct. Do not instantiate directly.
    @attr   gdb.Value   address     pointer to struct
    '''
    stype = None
    ptype = None
    def __init__(self, address):
        '''
        @param  gdb.Value   address     pointer to struct
        '''
        if str(address.type) != str(self.ptype):
            address = address.cast(self.ptype)
        self.address = address

    def get_member(self, member):
        '''
        @param String member: struct member to get
        '''
        return self.address.dereference()[member]

    def print_member(self, member):
        '''
        @param String member: struct member to print
        '''
        print("> '{0}': {1}".format(member, self.get_member(member)))

    def print_header(self):
        '''
        Info: prints type and address of the struct.
        '''
        # TODO use classvarible type
        print("{0} at {1}".format(self.address.dereference().type,
                                    self.address))

    def print_info(self):
        '''
        Info: Prints summary including 'interesting' members of the 
          struct. 
        '''
        self.print_header()
        self._print_info()
        print('')

    def _print_info(self):
        '''
        Implement yourself when subclassing.
        '''
        pass


class Task(GenericStruct):
    stype = g.lookup_type('struct task_struct')
    ptype = stype.pointer()
    def _print_info(self):
        self.print_member('pid')
        self.print_member('comm')


class Pipe(GenericStruct):
    stype = g.lookup_type('struct pipe_inode_info')
    ptype = stype.pointer()
    def _print_info(self):
        self.print_member('head')
        self.print_member('tail')
        self.print_member('ring_size')
        self.print_member('bufs')


class PipeBuffer(GenericStruct):
    stype = g.lookup_type('struct pipe_buffer')
    ptype = stype.pointer()
    def _print_info(self):
        print(self.address.dereference())


class File(GenericStruct):
    stype = g.lookup_type('struct file')
    ptype = stype.pointer()
    def get_filename(self):
        # TODO Maybe make it like page_address so it can be used as
        #   a convenience function without creating class instance
        return self.get_member('f_path')['dentry']['d_name']['name'].string()

    def _print_info(self):
        print('> filename: '+self.get_filename())


class AddrSpace(GenericStruct):
    stype = g.lookup_type('struct address_space')
    ptype = stype.pointer()
    def _print_info(self):
        print("> 'i_pages.xa_head' : {0}".format(
            self.get_member('i_pages')['xa_head']))


class XArray(GenericStruct):
    stype = g.lookup_type('struct xarray')
    ptype = stype.pointer()
    # TODO implement proper xarray functionality
    def _print_info(self):
        pass


class Page(GenericStruct):
    stype = g.lookup_type('struct page')
    ptype = stype.pointer()
    pagesize = 4096

    def __init__(self, address):
        '''
        @attr   gdb.Value   virtual     virtual address of cached data
        '''
        super().__init__(address)
        self.virtual = self.page_address(self.address)

    @staticmethod
    def page_address(page):
        '''
        Info: Calculates the virtual address of a page
        @param  gdb.Value   page        'struct page *'
        '''
        vmemmap_base = int(g.parse_and_eval('vmemmap_base'))
        page_offset_base = int(g.parse_and_eval('page_offset_base'))
        page = int(page)
        return (int((page - vmemmap_base)/64) << 12) + page_offset_base

    def _print_info(self):
        print("> data: "+str(g.selected_inferior().read_memory(self.virtual, 20).tobytes())+"[...]"+str(g.selected_inferior().read_memory(self.virtual+self.pagesize-20, 20).tobytes()))


'''
Breakpoint classes
'''
class GenericContextBP(g.Breakpoint):
    '''
    Info: A Breakpoint that is only active in a given context.
    '''
    def __init__(self, *args, **kwargs):
        '''
        @attr   String      comm        'comm' member of 'struct 
                                        task_struct' of process in whose 
                                        context we want to stop
        '''
        super().__init__(*args)
        self.comm = kwargs['comm']
        self._hit_count = 0
        self._condition = f"""$_streq($lx_current().comm, "{self.comm}")"""

    def stop(self):
        # Problem: It seems like the BP.condition only influences whether 
        #   gdb stops the program i.e. return value of stop(), but not if
        #   the code in stop() is executed.
        if( g.parse_and_eval(self._condition) == 0 ):
            return False
        self._hit_count += 1
        return self._stop()

    def _stop(self):
        pass


class OpenBP(GenericContextBP):
    def _stop(self):
        global task, file, fmap, page
        file = File(g.parse_and_eval('f'))
        if file.get_filename() != "target_file":
            return False
        task = Task(g.parse_and_eval('$lx_current()').address)
        fmap = AddrSpace(file.get_member('f_mapping'))
        page = Page(fmap.get_member('i_pages')['xa_head'])
        print(75*"-"+"\nStage 1: open the target file\n")
        task.print_info()
        file.print_info()
        fmap.print_info()
        page.print_info()
        return False


class PipeFcntlBP(GenericContextBP):
    def _stop(self):
        global pipe, buf 
        pipe = Pipe(g.parse_and_eval('file')['private_data'])
        buf = PipeBuffer(pipe.get_member('bufs'))
        print(75*"-"+"\nStage 2: create pipe\n")
        pipe.print_info()
        buf.print_info()
        return False


class PipeWriteBP(GenericContextBP):
    def _stop(self):
        global pipe, buf
        if int(buf.get_member('len')) not in {8, 18, 4096}:
            return False
        else:
            buf_page = Page(buf.get_member('page'))
            if int(buf.get_member('len')) == 8:
                print(75*"-"+"\nStage 3.1: init pipe buffer with write\n")
            elif int(buf.get_member('len')) == 4096:
                print(75*"-"+"\nStage 3.2: filled pipe buffer\n")
            else:
                global fmap
                print(75*"-"+"\nStage 7: writing into page cache\n")
                fmap.print_info()
        pipe.print_info()
        buf.print_info()
        buf_page.print_info()
        return False


class PipeReadBP(GenericContextBP):
    def _stop(self):
        global pipe, buf
        if int(buf.get_member('len')) != 0:
            return False
        print(75*"-"+"\nStage 4: release drained pipe buffer\n")
        pipe.print_info()
        buf.print_info()
        return False


class SpliceToPipeBP(GenericContextBP):
    def _stop(self):
        global fmap, pipe, buf, page 
        print(75*"-"+"\nStage 5: splicing file to pipe\n")
        pipe.print_info()
        buf.print_info()
        fmap.print_info()
        page.print_info()
        return False

'''
Instantiate breakpoints
'''
OpenBP('fs/open.c:1220', comm = 'poc')
PipeFcntlBP('fs/pipe.c:1401', comm = 'poc')
PipeWriteBP('fs/pipe.c:597', comm = 'poc')
PipeReadBP('fs/pipe.c:393', comm = 'poc')
SpliceToPipeBP('fs/splice.c:1106', comm = 'poc')
#PipeWriteBP('*0xffffffff8142005b', g.BP_HARDWARE_BREAKPOINT, comm = 'poc')
'''
gdb commands
'''
g.execute('c')
