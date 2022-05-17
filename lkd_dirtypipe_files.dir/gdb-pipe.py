import gdb as g
import re
class PipeBP(g.Breakpoint):
    def stop(self):
        pipe = g.parse_and_eval('pipe')
        bufs = pipe.dereference()['bufs']
        print(79*"-"+"\nStage: create pipe\n"
                "Address of 'struct pipe_inode_info': {0}\n"
                "> 'ring_size': {3}\n"
                "> 'bufs': {1}\n"
                "Contents of first 'struct pipe_buffer':\n{2}\n"
                .format(pipe, bufs, bufs.dereference(), 
                  pipe.dereference()['ring_size']))
        return False

class BufReleaseBP(g.Breakpoint):
    def stop(self):
        pipe = g.parse_and_eval('pipe')
        buf = g.parse_and_eval('buf')
        print(79*"-"+"\nStage: releasing drained 'struct pipe_buffer'\n"
                "Address of 'struct pipe_inode_info': {0}\n"
                "> 'ring_size': {3}\n"
                "> 'bufs': {4}\n"
                "Address of drained 'struct pipe_buffer': {1}\n"
                "> contents (after releasing):\n{2}\n"
                .format(pipe, buf, buf.dereference(),
                  pipe.dereference()['ring_size'],
                  pipe.dereference()['bufs']))
        return False

class CopyPageBP(g.Breakpoint):
    def stop(self):
        global writebp
        writebp.enabled = True
        pipe = g.parse_and_eval('i').dereference()['pipe']
        buf = pipe.dereference()['bufs']
        print(79*"-"+"\nStage: splicing file to pipe\n"
                "Address of 'struct pipe_inode_info': {0}\n"
                "> 'ring_size': {3}\n"
                "> 'bufs': {4}\n"
                "Address of target 'struct pipe_buffer': {1}\n"
                "> contents (after splicing):\n{2}\n"
                "Address of source 'struct address_space': {5}\n"
                "> Info: descibes an object in page cache\n"
                "> data page: {6}"
                .format(pipe, buf, buf.dereference(),
                  pipe.dereference()['ring_size'],
                  pipe.dereference()['bufs'],
                  re.findall(r'0x[0-9a-fA-F]+', g.execute(
                    'p $lx_current().files.fdt.fd[3].f_inode.i_mapping',
                    to_string=True))[0],
                  re.findall(r'0x[0-9a-fA-F]+', g.execute(
                    'p $lx_current().files.fdt.fd[3].f_inode.i_mapping'
                    '.i_pages.xa_head', to_string=True))[0]))
        return False

class WriteBP(g.Breakpoint):
    def stop(self):
        pipe = g.parse_and_eval('pipe')
        buf = pipe.dereference()['bufs']
        print(79*"-"+"\nStage: writing into page cache\n"
                "Address of 'struct pipe_inode_info': {0}\n"
                "> 'ring_size': {3}\n"
                "> 'bufs': {4}\n"
                "Address of 'struct pipe_buffer': {1}\n"
                "> contents (after appending):\n{2}\n"
                .format(pipe, buf, buf.dereference(),
                  pipe.dereference()['ring_size'],
                  pipe.dereference()['bufs']))
        g.execute('q')
        return False

PipeBP('fs/pipe.c:885')
BufReleaseBP('anon_pipe_buf_release')
CopyPageBP('lib/iov_iter.c:425')
writebp = WriteBP('*0xffffffff8120c94e', g.BP_HARDWARE_BREAKPOINT)
writebp.enabled = False
g.execute('c')
