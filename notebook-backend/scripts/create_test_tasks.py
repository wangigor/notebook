#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import uuid
import logging
from datetime import datetime

# Ensure we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db
from app.models.document import Document
from app.models.task import Task, TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_task(db, name, task_type, document_id=None):
    """Create a test task"""
    task_id = "test-task-{}".format(uuid.uuid4().hex[:8])
    
    # Create task object
    task = Task(
        id=task_id,
        name=name,
        task_type=task_type,
        created_by=1,  # Use user with ID 1
        document_id=document_id,
        status=TaskStatus.PENDING,
        progress=0.0,
        created_at=datetime.utcnow()
    )
    
    try:
        # Save to database
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info("Task created successfully: {}".format(task_id))
        return task
    except Exception as e:
        db.rollback()
        logger.error("Failed to create task: {}".format(str(e)))
        raise e

def update_existing_tasks(db):
    """Update existing test tasks, associate with documents"""
    # Get all documents
    documents = db.query(Document).limit(20).all()
    if not documents:
        logger.warn("No documents found, cannot associate tasks")
        return
    
    # Get all test tasks
    tasks = db.query(Task).filter(
        Task.id.like("test-task-%"),
        Task.document_id.is_(None)
    ).all()
    
    if not tasks:
        logger.warn("No unassociated test tasks found")
        return
    
    logger.info("Found {} test tasks and {} documents".format(len(tasks), len(documents)))
    
    # Associate a document with each task
    for i, task in enumerate(tasks):
        # Cycle through documents
        doc = documents[i % len(documents)]
        
        try:
            # Update task's document_id
            task.document_id = doc.id
            db.commit()
            logger.info("Task {} associated with document {}".format(task.id, doc.id))
        except Exception as e:
            db.rollback()
            logger.error("Failed to update task {}: {}".format(task.id, str(e)))

def main():
    """Main function"""
    # Get database session
    db = next(get_db())
    
    try:
        # Update existing test tasks
        update_existing_tasks(db)
        
        # Create some new test tasks
        documents = db.query(Document).limit(5).all()
        
        for i, doc in enumerate(documents):
            task_name = "Test Task {}".format(i+1)
            create_test_task(db, task_name, "TEST", doc.id)
            
        logger.info("Test tasks created and updated successfully")
        
    except Exception as e:
        logger.error("Operation failed: {}".format(str(e)))
    finally:
        db.close()

if __name__ == "__main__":
    main() 