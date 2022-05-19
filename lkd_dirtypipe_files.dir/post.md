# CVE-20??-???? 'Dirtypipe'
This blogpost reflects our exploration of the 'dirtypipe' bug in the Linux kernel. The bug was discovered by ?? and described in his original blogpost ??. 
While Max Kellermann's post is a great resource that contains all the relevant information to understand the bug, it assumes some familiartiy with the kernel. Initially, some of us were lacking this understanding and we had to dig into the relevant parts of the kernel to fully understand what's going on. It is the aim of this post to share our experiences and to provide a resource for other kernel novices that contains the technical information needed to obtain a solid understanding of the bug.
The idea of this post is as follows: We take a small  proof-of-concept (POC) program and divide it into stages. Each stage issues a systemcall, and we will look into the kernel to understand which actions and state changes happen in response to it. For this we will use both, the kernel source code [link] and a kernel debugging setup. We provide the debugging setup and the POC in a git repository in case you want to follow along.
Prereqisites: We assume familiartiy with operating system (OS) abstactions like virtual memory, files, ...
## 'Opening & mapping a file' | Concept: Page Cache
Text: caching for performance - cache is what matters - file mappings 

Kernel source: cache hit/miss, caching file, creating fd entry

Debugging: get struct task_struct, struct address_space, struct page & data of page

## 'Creating a pipe' | Concept: Pipes
Text: unidirectional IPC mechanism - ring buffer

Kernel source: alloc pipe inode, register fds with proc, file operations

Debugging: get struct pipe_inode_info

### Userland
From a user perspective, a pipe consists of two file desciptors, one for reading and one for writing. A read on the former shall return the data written to the latter on a first-in-first-out basis. On x86-64 Linux a process creates a pipe by means of the 'sys_pipe' systemcall i.e., executing int 0x80 with rax set to 22 and rdi pointing to the integer array which is to hold the file desciptors.

### Kernelspace
On a very higzah level, the kernel thinks of a pipe as a circular buffer. There are two positions in this buffer: one for writing to (the 'head') - and one for reading from (the 'tail') the pipe.
A bit more technically speaking, a pipe is represented by a 'struct pipe_inode_info' (pipe_fs_i.h:58) whose member 'bufs' holds a pointer to a list of 'struct pipe_buffer' (pipe_fs_i.h:26), which make up the circular buffer. If a process asks for a new pipe, the kernel creates it by calling 'alloc_pipe_info(void)' (pipe.c:780). This function allocates space for the 'struct pipe_inode_info' as well as all the 'struct pipe_buffer'. Furthermore, it initializes some values in, and returns a pointer to, the former.
When a process whishes to 'write()' to a pipe, the kernel handles this by calling 'pipe_write(struct kiocb *iocb, struct iov_iter *from)' (pipe.c:413). Each entry in the ring of 'struct pipe_buffer' has a 'page' member, which points to the 'struct page' (??) representing the page of physical memory holding the buffer's data. When writing to a pipe, the kernel first checks if it can append (part of) the data to 'page' of 'pipe_buffer' that is currently the 'head' of the ring. Whether this is possible is decided by two things: first if there is enough space left on the page and second if the 'pipe_buffer' has the 'PIPE_BUF_FLAG_CAN_MERGE' set. To complete the rest of the write the kernel advances the 'head' to the next 'pipe_buffer', allocates a 'page', initializes the flags (the can merge flag will be set, unless the user explicitly asked for the pipe to be in 'O_DIRECT' mode), and writes the data to the new page. This continues until there is no data left or the pipe is full.
The case where a process asks the kernel to read() from a pipe is handeled by the function 'pipe_read(struct kiocb *iocb, struct iov_iter *to)' (pipe.c:230). If the pipe is non-empty, the data is taken from the 'pipe_buffer' at 'tail' (pipe.c:305). In case the 'pipe_buffer' at tail was emptied by this read, the 'release' function pointer of the 'ops' member of the 'pipe_buffer' is executed (pipe.c:322, pipe_fs_i.h:211). For a 'pipe_buffer' that was initialized by an earlier 'write()', the 'ops' member is a pointer to the 'struct pipe_buf_operations anon_pipe_buf_ops' (pipe.c:521, pipe.c:213). Thus, 'anon_pipe_buf_release(struct pipe_inode_info *pipe, struct pipe_buffer *buf)' is executed (pipe.c:124), which calls 'put_page' to release our reference to the page. Note that while the 'ops' pointer is nulled, the 'page' and 'flags' members of 'pipe_buffer' are left unmodified.
For us the key takeaways are:
1. writes to a pipe can append to the 'page' of a 'pipe_buffer' (pipe.c:466)
2. the can-merge flag is set by default for buffers initialized by writes (pipe.c:527)
3. emptying a 'pipe_buffer' initialized by a write() with a read() leaves the can-merge flag set
However, write()'ing to a pipe is not the only way fill it...

## 'Writing & reading a pipe' | Concept: Ring buffer, merging, releasing
Text: file operations - writes that create new anon page (flag init) - wites that merge - reads that emply a page (no deinit)

Kernel source: pipe inode file operations - pipe_write - pipe_read - anon_buf_release

Debugging: evolution of struct pipe_buffer

## 'Splicing to a pipe' | Concept: zero copy
Text: why splice is efficient 

Kernel source: copy_page_to_iter_pipe

Debugging: show that indeed pipe_buffer and address_space refer to the same stuct page, show that flags are still set from earlier (we reuse the buffer)

### Userland
A process can ask for a filedescriptor for a particular file using the 'sys_open' systemcall (rax: 2, rdi: char *filename, rsi: int flags, rdx: int mode). If the process wishes to fill the file (or a part of it) into a pipe there are different possibilities. It could read() the data into a buffer in it's memory (or mmap() the file) and then write() it to the pipe. However, this is as inefficient as it sounds (the user-kernel boundary has to be chrossed three times, I guess the latter is still better than the former). To make this whole operation more efficient there exists the 'sys_splice' systemcall (rax: 275, rdi: int fd_in, rsi: loff_t *off_in, rdx: int fd_out, r10: loff_t *off_out, r8: size_t len, r9: uint flags). It eliminates the need to make the data from the file available in the process' virtual address space by asking the kernel to move it directly between the filedescriptors of the file and the pipe, thus reducing the cost of the operation by one. But what is the kernel actually doing?

### Kernelspace
#### Diagression: Dispatching a systemcall
It is fun to dive into what happens after a process has diligently set up its registers and executed a 'syscall' instruction. First of all, it depends on how the kernel has set up the CPU at some earlier stage, probably during startup. This is an interesting topic in its own right, but here I want to focus on the case where everything is already set up. Everything starts at '/arch/x86/entry/entry_64.S:87' where the low-level system-call handling routine starts. The code is heavily obfuscated through the extensive use of macros ;), however, I guess it starts by switching the stack to kernel stack for the process. Afterwards it builds a 'struct pt_regs' (/arch/x86/include/uapi/asm/ptrace.h:18) representing the process' registers state when it executed the the 'syscall' on this stack and calls 'do_syscall_64' with the syscall number and a pointer to this struct. Then we call 'do_syscall_x64' (/arch/x86/entry/common.c:40), which essentially only uses the syscall number as an index to the 'sys_call_table' of function pointers implenting the actual syscall logic and calls it with the 'pt_regs *' as an argument. But finding the actual implementation from here is not that easy due to marco magic. The table is filled here '/arch/x86/entry/syscall_64.c', from here '/include/generated/asm/syscalls_64.h', where the macro is denfined here 'arch/x86/entry/syscall_64.c' and the function prototype '/include/linux/syscalls.h:545' is 'asmlinkage' to indicate the nonstandard calling convention used. The actual implementation of 'sys_splice' filling this prototype with life is here '/fs/splice.c:1332', where the macro is used to make additional metadata about the syscall available. Tracking down the marco chain indeed confirms that is links the implementation to the correct entry in the 'sys_call_table' '/include/linux/syscalls.h:242'.

#### Page Cache
Fetching data from permanent storage is slow. Really slow.
#### splice()'ing to a pipe
Where does the pointer to the page ino the page cache gets set in the pipe_buffer. Where are existing buffers with initialized flags reused instead on initializing a new pipe_buffer with fresh flags.
## 'Writing into the page cache' | Analysis: Two perspectives on one page
Text: permission checks long gone, two perspecives explain: why can't make file larger, why cant overwrite first byte, why cant write across pages

Kernel source (covered earlier)

Debugging: show that we go down append path on next write, len field of pipe_buffer changes, print data in page cache from reference we saved earlier
## Conclusion
Text: Takeaways for approaches for understanding OS bugs, exploitation ideas, 
