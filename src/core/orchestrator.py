```python src/core/orchestrator.py
from typing import List, Dict, Optional
from src.core import task_scheduler
import time
import logging

logger = logging.getLogger(__name__)

class OrchestrationEngine:
    def __init__(self):
        self.workflow_registry = {}
    
    def define_workflow(self, 
                       workflow_id: str, 
                       task_chain: List[str], 
                       retry_policy: Dict = None,
                       timeout: Optional[int] = None):
        """
        Register a workflow with chaining, retry, and timeout policies
        """
        self.workflow_registry[workflow_id] = {
            "chain": task_chain,
            "retry": retry_policy or {"max_retries": 3, "backoff": 2},
            "timeout": timeout or 300  # 5 minutes
        }
    
    def execute(self, workflow_id: str, context: Dict = None):
        workflow = self.workflow_registry.get(workflow_id)
        if not workflow:
            raise ValueError(f"Unknown workflow ID: {workflow_id}")
        
        for task_id in workflow["chain"]:
            start_time = time.time()
            
            while start_time + workflow["timeout"] > time.time():
                try:
                    result = task_scheduler.run_task(task_id, context)
                    context["outputs"] = result
                    break
                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}")
                    if workflow["retry"]["max_retries"] > 0:
                        time.sleep(workflow["retry"]["backoff"])
                        workflow["retry"]["max_retries"] -= 1
                    else:
                        raise
        return context["outputs"]
```

---

### ✅ **Step 2: Create Scalable Deployment Templates**  
**Task B** – Helm charts for Kubernetes  

```tool
TOOL_NAME: file_glob_search
BEGIN_ARG: pattern
deploy/helm/**