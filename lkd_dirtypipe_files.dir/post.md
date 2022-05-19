# The Dirty Pipe Vulnerability - CVE-2022-0847

This blog post reflects our exploration of the Dirty Pipe Vulnerability in the Linux kernel. The bug was discovered by Max Kellermann and described in his original [blog post](https://dirtypipe.cm4all.com/). While Kellermann's post is a great resource that contains all the relevant information to understand the bug, it assumes some familiarity with the kernel. To fully understand what's going on we shed some more light on some Linux kernel internals. The aim of this post is to share our knowledge and to provide a resource for other interested individuals.
The idea of this post is as follows: We take a small  proof-of-concept (PoC) program and divide it into several stages. Each stage issues a system call, and we will look into the kernel to understand which actions and state changes happen in response to those calls. For this we use both, the kernel source code (https://elixir.bootlin.com/linux/v5.17.9/source) and a kernel debugging setup (derived from https://github.com/martinclauss/linux-kernel-debugging). We Dirty Pipe-specific debugging setup and the PoC code is provided in a GitHub repository for your convenience at: TODO

## 'Opening & mapping a file' | Concept: Page Cache
Text: caching for performance - cache is what matters - file mappings 

Kernel source: cache hit/miss, caching file, creating fd entry

Debugging: get struct task_struct, struct address_space, struct page & data of page

#### Page Cache
Fetching data from permanent storage is slow. Really slow.

## 'Creating a pipe' | Concept: Pipes
Text: unidirectional IPC mechanism - ring buffer

Kernel source: alloc pipe inode, register fds with proc, file operations

Debugging: get struct pipe_inode_info

### Userland
From a user perspective, a pipe consists of two file desciptors, one for reading and one for writing. A read on the former shall return the data written to the latter on a first-in-first-out basis. On x86-64 Linux a process creates a pipe by means of the 'sys_pipe' systemcall.

### Kernelspace
On a very high level, the kernel thinks of a pipe as a circular buffer. There are two positions in this buffer: one for writing to (the 'head') - and one for reading from (the 'tail') the pipe.
A bit more technically speaking, a pipe is represented by a 'struct pipe_inode_info' (pipe_fs_i.h:58) whose member 'bufs' holds a pointer to a list of 'struct pipe_buffer' (pipe_fs_i.h:26), which make up the circular buffer. If a process asks for a new pipe, the kernel creates it by calling 'alloc_pipe_info(void)' (pipe.c:780). This function allocates space for the 'struct pipe_inode_info' as well as all the 'struct pipe_buffer'. Furthermore, it initializes some values in, and returns a pointer to, the former.

## 'Writing & reading a pipe' | Concept: Ring buffer, merging, releasing
Text: file operations - writes that create new anon page (flag init) - wites that merge - reads that emply a page (no deinit)

Kernel source: pipe inode file operations - pipe_write - pipe_read - anon_buf_release

Debugging: evolution of struct pipe_buffer

When a process whishes to 'write()' to a pipe, the kernel handles this by calling 'pipe_write(struct kiocb *iocb, struct iov_iter *from)' (pipe.c:413). Each entry in the ring of 'struct pipe_buffer' has a 'page' member, which points to the 'struct page' (??) representing the page of physical memory holding the buffer's data. When writing to a pipe, the kernel first checks if it can append (part of) the data to 'page' of 'pipe_buffer' that is currently the 'head' of the ring. Whether this is possible is decided by two things: first if there is enough space left on the page and second if the 'pipe_buffer' has the 'PIPE_BUF_FLAG_CAN_MERGE' set. To complete the rest of the write the kernel advances the 'head' to the next 'pipe_buffer', allocates a 'page', initializes the flags (the can merge flag will be set, unless the user explicitly asked for the pipe to be in 'O_DIRECT' mode), and writes the data to the new page. This continues until there is no data left or the pipe is full.
The case where a process asks the kernel to read() from a pipe is handeled by the function 'pipe_read(struct kiocb *iocb, struct iov_iter *to)' (pipe.c:230). If the pipe is non-empty, the data is taken from the 'pipe_buffer' at 'tail' (pipe.c:305). In case the 'pipe_buffer' at tail was emptied by this read, the 'release' function pointer of the 'ops' member of the 'pipe_buffer' is executed (pipe.c:322, pipe_fs_i.h:211). For a 'pipe_buffer' that was initialized by an earlier 'write()', the 'ops' member is a pointer to the 'struct pipe_buf_operations anon_pipe_buf_ops' (pipe.c:521, pipe.c:213). Thus, 'anon_pipe_buf_release(struct pipe_inode_info *pipe, struct pipe_buffer *buf)' is executed (pipe.c:124), which calls 'put_page' to release our reference to the page. Note that while the 'ops' pointer is nulled, the 'page' and 'flags' members of 'pipe_buffer' are left unmodified.
For us the key takeaways are:
1. writes to a pipe can append to the 'page' of a 'pipe_buffer' (pipe.c:466)
2. the can-merge flag is set by default for buffers initialized by writes (pipe.c:527)
3. emptying a 'pipe_buffer' initialized by a write() with a read() leaves the can-merge flag set
However, write()'ing to a pipe is not the only way fill it...

## 'Splicing to a pipe' | Concept: zero copy
Text: why splice is efficient 

Kernel source: copy_page_to_iter_pipe

Debugging: show that indeed pipe_buffer and address_space refer to the same stuct page, show that flags are still set from earlier (we reuse the buffer)

### Userland
A process can ask for a filedescriptor for a particular file using the 'sys_open' systemcall (rax: 2, rdi: char *filename, rsi: int flags, rdx: int mode). If the process wishes to fill the file (or a part of it) into a pipe there are different possibilities. It could read() the data into a buffer in it's memory (or mmap() the file) and then write() it to the pipe. However, this is as inefficient as it sounds (the user-kernel boundary has to be chrossed three times, I guess the latter is still better than the former). To make this whole operation more efficient there exists the 'sys_splice' systemcall (rax: 275, rdi: int fd_in, rsi: loff_t *off_in, rdx: int fd_out, r10: loff_t *off_out, r8: size_t len, r9: uint flags). It eliminates the need to make the data from the file available in the process' virtual address space by asking the kernel to move it directly between the filedescriptors of the file and the pipe, thus reducing the cost of the operation by one. But what is the kernel actually doing?

### Kernelspace

#### splice()'ing to a pipe
Where does the pointer to the page ino the page cache gets set in the pipe_buffer? Where are existing buffers with initialized flags reused instead on initializing a new pipe_buffer with fresh flags?

## 'Writing into the page cache' | Analysis: Two perspectives on one page
Text: permission checks long gone, two perspecives explain: why can't make file larger, why cant overwrite first byte, why cant write across pages

Kernel source (covered earlier)

Debugging: show that we go down append path on next write, len field of pipe_buffer changes, print data in page cache from reference we saved earlier
## Conclusion
Text: Takeaways for approaches for understanding OS bugs, exploitation ideas, 
