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
        
    async def yielder(self, async_generator):
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
            pass
        
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
    
    async def run(self, *args, **kwargs):
        task = None
        
        if self.running_loop:
            task = self.create_task(*args, **kwargs)
        else:
            from asyncio import run as asyncio_run
            task = asyncio_run(*args, **kwargs)
            
        self.task_set.add(task)
        await self.gather(task_set)
        return task
    
    def create_task(self, *args, **kwargs):
        self.running_loop = self.get_event_loop()
        if self.running_loop:
            task = self.running_loop.create_task(*args, **kwargs)
        else:
            
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=DeprecationWarning)
                from asyncio import create_task as asyncio_create_task
            
            task = asyncio_create_task(*args, **kwargs)
        
        self.task_set.add(task)
        return task
        
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
        self.running_loop = self.is_event_loop_running(*args, **kwargs)
        
        return self.running_loop
        
    