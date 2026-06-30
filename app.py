import sys
from typing import Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from supabase import create_client, Client

# ==========================================================
# 1. INITIALIZATION & CONFIG
# ==========================================================
GEMINI_API_KEY = "AQ.Ab8RN6KWf80I64TN_4-O2WSMZ6U3NESUn3arouycPK60avWXVw"
SUPABASE_URL = "https://bpenmhytwhbkdphcwoqi.supabase.co"
SUPABASE_KEY = "sb_secret_DIcOZ7vVm9i-vvLEx-xjHg_IgbNUR9Q"

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"❌ Error initializing services: {e}")
    sys.exit(1)


# ==========================================================
# 2. SCHEMAS & CALCULATIONS (Updated with new defaults)
# ==========================================================
class ExtractedTask(BaseModel):
    task_name: str = Field(..., description="The clean name or description of the task.")
    days_until_deadline: int = Field(
        default=1, 
        description="Days until deadline. Strict default is 1 if not explicitly mentioned."
    )
    estimated_hours: int = Field(
        default=1, 
        description="Hours estimated to complete. Strict default is 1 if not explicitly mentioned."
    )
    importance: Literal["high", "medium", "low"] = Field(
        default="low", 
        description="Importance level. Strict default is 'low' if not explicitly mentioned."
    )


def calculate_priority_score(task: ExtractedTask) -> int:
    # Use the attributes directly as they are now guaranteed non-null ints/strs
    days = task.days_until_deadline
    if days <= 0:
        urgency_points = 60
    elif 1 <= days <= 7:
        urgency_points = 30
    elif 8 <= days <= 30:
        urgency_points = 10
    else:
        urgency_points = 0
    
    importance = task.importance.lower().strip()
    importance_points = 50 if importance == "high" else (30 if importance == "medium" else 10)
    
    hours = task.estimated_hours
    size_points = 40 if hours > 10 else (20 if 3 <= hours <= 10 else 10)
    
    return urgency_points + importance_points + size_points


def save_to_supabase(task: ExtractedTask, score: int):
    # Ultimate runtime safety fallback block before pushing to DB 
    payload = {
        "task_name": task.task_name,
        "days_until_deadline": task.days_until_deadline if task.days_until_deadline is not None else 1,
        "estimated_hours": task.estimated_hours if task.estimated_hours is not None else 1,
        "importance": task.importance if task.importance is not None else "low",
        "priority_score": score
    }
    try:
        return supabase_client.table("tasks").insert(payload).execute()
    except Exception as e:
        print(f"❌ Failed to save task to Supabase: {e}")
        return None


def get_all_tasks():
    try:
        response = supabase_client.table("tasks").select("*").order("priority_score", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"❌ Failed to fetch task list: {e}")
        return []


def process_and_add_task(user_input: str):
    print("\n🤖 Processing with AI...")
    prompt = f'Analyze the user input and extract task details.\nUser input: "{user_input}"'
    
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': ExtractedTask}
        )
        extracted = response.parsed if hasattr(response, 'parsed') and response.parsed else ExtractedTask.model_validate_json(response.text)
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return

    score = calculate_priority_score(extracted)
    db_response = save_to_supabase(extracted, score)
    
    if db_response:
        print("\n🎉 Success! Task securely saved to your remote Supabase database.")
        print(f"📊 Extracted Data: {extracted.model_dump()}")
        print(f"📈 Calculated Priority Score: {score}")
    else:
        print("❌ Error saving task to Supabase.")


def display_task_list():
    print("\n" + "="*50)
    print("📋 Your Prioritized Task List")
    print("="*50)
    
    tasks = get_all_tasks()
    if tasks:
        for index, task in enumerate(tasks):
            badge = "🔴" if task['importance'] == 'high' else ("🟡" if task['importance'] == 'medium' else "🟢")
            print(f"{index + 1}. {task['task_name']}")
            print(f"   Score: {task['priority_score']} | Deadline: {task['days_until_deadline']} days | Est: {task['estimated_hours']}h | Importance: {badge} {task['importance'].upper()}")
            print("-" * 40)
    else:
        print("No tasks recorded yet. Try adding one!")


if __name__ == "__main__":
    print("🎙️ Intelligent Task Prioritizer (CLI Edition)")
    
    while True:
        print("\nOptions: [1] Add New Task  [2] View Prioritized List  [3] Exit")
        choice = input("Select an option (1-3): ").strip()
        
        if choice == "1":
            user_text = input("\nType your task description:\n> ").strip()
            if user_text:
                process_and_add_task(user_text)
            else:
                print("Task cannot be empty.")
        elif choice == "2":
            display_task_list()
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please select 1, 2, or 3.")