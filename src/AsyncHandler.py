class AsyncHandler():
    from src.utils import PrintLogger
    
    def __init__(self, dump_info = PrintLogger.register('AsyncHandler')):   
        self.queues = {}
        self.task_set = set()
        self.dump_info = dump_info
        
        self.running_loop = None
    
    async def __exit__(self, exc_type, exc_value, exc_traceback):
        with self.dump_info('Exiting AsyncHandler'):
            pending = asyncio.Task.all_tasks()
            for task in pending:
                task.cancel()
            asyncio.run(asyncio.gather(*pending))

            for q in self.queues.values():
                await q.join()

            if exc_type:
                print(exc_type, exc_value, exc_traceback)
        
    @classmethod
    async def yielder(cls, async_generator):
        item = None
        async for i in async_generator():
            item = i
            break
        return item
        
    def add_queue(self, name):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            from asyncio import Queue as asyncio_Queue
        if name in self.queues:
            self.dump_info().log(f'Queue {name} already exists.')
        else:
            self.queues[name] = asyncio_Queue()
        return self.get_queue(name)
        
    def get_queue(self, name):
        return self.queues[name]
    
    async def add_task(self, queue, task):
        await self.queues[queue].put(task)
        
    def gather(self, *args, **kwargs):
    
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            from asyncio import gather as asyncio_gather
        
        return asyncio_gather(*args, **kwargs)
    
    def run(self, func, *func_args):       
        if self.is_event_loop_running():
            self.dump_info().log(f'Running loop detected: call asyncio.create_task on {func} manually.', important=True)
            return False
        else:
            self.running_loop = self.get_event_loop() 
            from asyncio import run as asyncio_run
            from asyncio import gather as asyncio_gather
            from asyncio import new_event_loop as asyncio_new_loop
            with self.dump_info(f'Start running loop for {func}.'):
                #asyncio_run(func(*func_args))
                self.running_loop = asyncio_new_loop()
                task = self.create_task(func(*func_args))
                #asyncio_gather(task)
                #self.running_loop.run_forever()
            return True
    
    def create_task(self, *args, **kwargs):
        self.dump_info().log(f'Creating task {args}')
        if not self.running_loop:
            self.running_loop = self.get_event_loop()
        
        task = self.running_loop.create_task(*args, **kwargs)

        self.task_set.add(task)
        return task
    
    async def create_n_wait(self, *args, **kwargs):
        await self.create_task(*args, **kwargs)
        
    def is_event_loop_running(self, *args, **kwargs):
        
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            from asyncio import get_event_loop as asyncio_get_event_loop
        
        loop = None
        try:
            loop = asyncio_get_event_loop(*args, **kwargs)
        except RuntimeError as e:
            print(e)
        
        if loop and loop.is_running():
            return loop
        elif loop:
            pass
        else:
            #from asyncio import new_event_loop as asyncio_new_event_loop
            #self.running_loop = asyncio_new_event_loop()
            return None    

    def get_event_loop(self, *args, **kwargs):
        loop = self.is_event_loop_running(*args, **kwargs)
        
        if loop:
            return loop
        else:
            from asyncio import create_event_loop as async_create_event_loop
            return async_create_event_loop()
        
    async def sleep(self, duration):
        from asyncio import sleep as asyncio_sleep
        await asyncio_sleep(duration)
    