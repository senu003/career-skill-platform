from sqlalchemy.orm import Session
from app.models import AssessmentQuestion, QuestionOption

INITIAL_QUESTIONS = [
    # JAVASCRIPT — BASIC
    {
        "skill": "JavaScript",
        "level": "basic",
        "topic": "Variables",
        "question": "Which keyword is used to declare a variable that cannot be reassigned?",
        "correct_answer": "C",
        "options": {"A": "var", "B": "let", "C": "const", "D": "static"}
    },
    {
        "skill": "JavaScript",
        "level": "basic",
        "topic": "Data Types",
        "question": "Which of the following is a JavaScript primitive data type?",
        "correct_answer": "C",
        "options": {"A": "Array", "B": "Object", "C": "String", "D": "Function"}
    },
    {
        "skill": "JavaScript",
        "level": "basic",
        "topic": "Arrays",
        "question": "Which method adds an element to the end of a JavaScript array?",
        "correct_answer": "A",
        "options": {"A": "push()", "B": "pop()", "C": "shift()", "D": "unshift()"}
    },
    {
        "skill": "JavaScript",
        "level": "basic",
        "topic": "Functions",
        "question": "Which syntax correctly defines a JavaScript function?",
        "correct_answer": "A",
        "options": {"A": "function greet() { }", "B": "def greet() { }", "C": "func greet() { }", "D": "function: greet() { }"}
    },
    {
        "skill": "JavaScript",
        "level": "basic",
        "topic": "Conditions",
        "question": "Which operator checks both value and type equality?",
        "correct_answer": "C",
        "options": {"A": "=", "B": "==", "C": "===", "D": "!="}
    },
    # JAVASCRIPT — INTERMEDIATE
    {
        "skill": "JavaScript",
        "level": "intermediate",
        "topic": "Array Methods",
        "question": "What does the map() method normally return?",
        "correct_answer": "B",
        "options": {"A": "The original array only", "B": "A new array", "C": "A boolean", "D": "A string"}
    },
    {
        "skill": "JavaScript",
        "level": "intermediate",
        "topic": "Array Methods",
        "question": "What does filter() return?",
        "correct_answer": "A",
        "options": {"A": "A new array containing elements that satisfy a condition", "B": "The first element matching a condition", "C": "A boolean", "D": "The number of matching elements"}
    },
    {
        "skill": "JavaScript",
        "level": "intermediate",
        "topic": "Async JavaScript",
        "question": "What does an async function return?",
        "correct_answer": "C",
        "options": {"A": "A string", "B": "An array", "C": "A Promise", "D": "A callback"}
    },
    {
        "skill": "JavaScript",
        "level": "intermediate",
        "topic": "Promises",
        "question": "Which keyword is normally used to wait for a Promise inside an async function?",
        "correct_answer": "B",
        "options": {"A": "wait", "B": "await", "C": "pause", "D": "async"}
    },
    {
        "skill": "JavaScript",
        "level": "intermediate",
        "topic": "Scope",
        "question": "What is a major difference between let and var?",
        "correct_answer": "A",
        "options": {"A": "let is block-scoped while var is function-scoped", "B": "var is block-scoped while let is function-scoped", "C": "They always have exactly the same scope", "D": "let cannot store numbers"}
    },
    # JAVASCRIPT — ADVANCED
    {
        "skill": "JavaScript",
        "level": "advanced",
        "topic": "Closures",
        "question": "What is a closure in JavaScript?",
        "correct_answer": "A",
        "options": {"A": "A function that remembers variables from its outer scope", "B": "A function that always returns an object", "C": "A method used to close browser windows", "D": "A special type of loop"}
    },
    {
        "skill": "JavaScript",
        "level": "advanced",
        "topic": "Event Loop",
        "question": "What is the main purpose of the JavaScript event loop?",
        "correct_answer": "B",
        "options": {"A": "Compile JavaScript into machine code", "B": "Manage asynchronous callbacks and execution", "C": "Create HTML elements", "D": "Store variables permanently"}
    },
    {
        "skill": "JavaScript",
        "level": "advanced",
        "topic": "Promises",
        "question": "Which Promise method runs when a Promise is rejected?",
        "correct_answer": "C",
        "options": {"A": "then()", "B": "resolve()", "C": "catch()", "D": "finallyOnly()"}
    },
    {
        "skill": "JavaScript",
        "level": "advanced",
        "topic": "Destructuring",
        "question": "What does this code do?\n\nconst { name, age } = user;",
        "correct_answer": "B",
        "options": {"A": "Creates a new user object", "B": "Extracts name and age properties from user", "C": "Deletes name and age", "D": "Converts user to an array"}
    },
    {
        "skill": "JavaScript",
        "level": "advanced",
        "topic": "Functional Programming",
        "question": "What is a key difference between reduce() and map()?",
        "correct_answer": "A",
        "options": {"A": "reduce() can transform an array into a single accumulated value", "B": "map() can only work with numbers", "C": "reduce() cannot use functions", "D": "They always produce exactly the same result"}
    },

    # REACT — BASIC
    {
        "skill": "React",
        "level": "basic",
        "topic": "Components",
        "question": "What is a React component?",
        "correct_answer": "A",
        "options": {"A": "A reusable UI building block", "B": "A database table", "C": "A CSS file", "D": "A backend server"}
    },
    {
        "skill": "React",
        "level": "basic",
        "topic": "JSX",
        "question": "What is JSX mainly used for in React?",
        "correct_answer": "B",
        "options": {"A": "Writing SQL queries", "B": "Describing UI structure using JavaScript-like syntax", "C": "Creating database connections", "D": "Managing HTTP servers"}
    },
    {
        "skill": "React",
        "level": "basic",
        "topic": "Props",
        "question": "What are props mainly used for?",
        "correct_answer": "A",
        "options": {"A": "Passing data from a parent component to a child component", "B": "Storing data permanently in a database", "C": "Styling only", "D": "Creating API endpoints"}
    },
    {
        "skill": "React",
        "level": "basic",
        "topic": "State",
        "question": "Which React Hook is commonly used to manage component state?",
        "correct_answer": "A",
        "options": {"A": "useState", "B": "useRoute", "C": "useServer", "D": "useDatabase"}
    },
    {
        "skill": "React",
        "level": "basic",
        "topic": "Lists",
        "question": "Why should React list items usually have a key prop?",
        "correct_answer": "A",
        "options": {"A": "To help React identify list items efficiently", "B": "To encrypt the list", "C": "To make CSS work", "D": "To connect the list to a database"}
    },
    # REACT — INTERMEDIATE
    {
        "skill": "React",
        "level": "intermediate",
        "topic": "useEffect",
        "question": "What is useEffect() commonly used for?",
        "correct_answer": "A",
        "options": {"A": "Handling side effects such as API calls", "B": "Creating CSS classes", "C": "Defining database tables", "D": "Replacing JSX"}
    },
    {
        "skill": "React",
        "level": "intermediate",
        "topic": "State Updates",
        "question": "What is the recommended way to update state based on its previous value?",
        "correct_answer": "B",
        "options": {"A": "Directly modify the state variable", "B": "Use the functional form of the state setter", "C": "Refresh the browser", "D": "Modify the DOM directly"}
    },
    {
        "skill": "React",
        "level": "intermediate",
        "topic": "Controlled Components",
        "question": "What is a controlled input in React?",
        "correct_answer": "A",
        "options": {"A": "An input whose value is controlled by React state", "B": "An input controlled only by CSS", "C": "An input that cannot be edited", "D": "An input stored directly in PostgreSQL"}
    },
    {
        "skill": "React",
        "level": "intermediate",
        "topic": "Component Communication",
        "question": "How can a child component commonly communicate an event to its parent?",
        "correct_answer": "A",
        "options": {"A": "By calling a callback function passed through props", "B": "By directly changing the parent's state variable", "C": "By changing the database", "D": "By restarting React"}
    },
    {
        "skill": "React",
        "level": "intermediate",
        "topic": "Conditional Rendering",
        "question": "Which is a common way to conditionally render JSX?",
        "correct_answer": "A",
        "options": {"A": "Using a JavaScript condition such as a ternary operator", "B": "Using SQL", "C": "Using Python decorators", "D": "Using Docker"}
    },
    # REACT — ADVANCED
    {
        "skill": "React",
        "level": "advanced",
        "topic": "Performance",
        "question": "What is useMemo() primarily intended to do?",
        "correct_answer": "A",
        "options": {"A": "Memoize a calculated value", "B": "Make API requests", "C": "Create a new component", "D": "Store data in PostgreSQL"}
    },
    {
        "skill": "React",
        "level": "advanced",
        "topic": "Performance",
        "question": "What is useCallback() primarily used for?",
        "correct_answer": "A",
        "options": {"A": "Memoizing a function reference", "B": "Creating database tables", "C": "Fetching images", "D": "Replacing useState"}
    },
    {
        "skill": "React",
        "level": "advanced",
        "topic": "Rendering",
        "question": "Why can changing a component's state cause it to render again?",
        "correct_answer": "A",
        "options": {"A": "React needs to update the UI based on the new state", "B": "The browser must restart", "C": "PostgreSQL automatically sends a request", "D": "JavaScript variables cannot change"}
    },
    {
        "skill": "React",
        "level": "advanced",
        "topic": "State Architecture",
        "question": "When is a global state management solution particularly useful?",
        "correct_answer": "A",
        "options": {"A": "When state needs to be shared across many unrelated components", "B": "When rendering one static paragraph", "C": "When writing CSS", "D": "When creating a PostgreSQL table"}
    },
    {
        "skill": "React",
        "level": "advanced",
        "topic": "Hooks",
        "question": "What is an important rule when using React Hooks?",
        "correct_answer": "A",
        "options": {"A": "Hooks should generally be called at the top level of React components or custom Hooks", "B": "Hooks should always be called inside loops", "C": "Hooks can only be called inside event handlers", "D": "Hooks should only be called from CSS"}
    },

    # POSTGRESQL — BASIC
    {
        "skill": "PostgreSQL",
        "level": "basic",
        "topic": "SELECT",
        "question": "Which SQL statement retrieves data from a table?",
        "correct_answer": "B",
        "options": {"A": "GET", "B": "SELECT", "C": "FETCHTABLE", "D": "READ"}
    },
    {
        "skill": "PostgreSQL",
        "level": "basic",
        "topic": "INSERT",
        "question": "Which SQL command adds a new row to a table?",
        "correct_answer": "B",
        "options": {"A": "ADD", "B": "INSERT", "C": "CREATE ROW", "D": "APPEND TABLE"}
    },
    {
        "skill": "PostgreSQL",
        "level": "basic",
        "topic": "Primary Keys",
        "question": "What is the main purpose of a primary key?",
        "correct_answer": "A",
        "options": {"A": "Uniquely identify rows in a table", "B": "Store passwords", "C": "Sort every column automatically", "D": "Create a backup"}
    },
    {
        "skill": "PostgreSQL",
        "level": "basic",
        "topic": "Filtering",
        "question": "Which SQL clause is used to filter rows?",
        "correct_answer": "A",
        "options": {"A": "WHERE", "B": "FILTER", "C": "SELECTED", "D": "HAVING ONLY"}
    },
    {
        "skill": "PostgreSQL",
        "level": "basic",
        "topic": "Database Structure",
        "question": "What is a table in a relational database?",
        "correct_answer": "A",
        "options": {"A": "A collection of rows and columns", "B": "A programming function", "C": "A server", "D": "A network connection"}
    },
    # POSTGRESQL — INTERMEDIATE
    {
        "skill": "PostgreSQL",
        "level": "intermediate",
        "topic": "JOIN",
        "question": "What is the purpose of a JOIN?",
        "correct_answer": "A",
        "options": {"A": "Combine related data from multiple tables", "B": "Delete duplicate databases", "C": "Create a server", "D": "Encrypt data"}
    },
    {
        "skill": "PostgreSQL",
        "level": "intermediate",
        "topic": "GROUP BY",
        "question": "What is GROUP BY commonly used for?",
        "correct_answer": "A",
        "options": {"A": "Grouping rows so aggregate calculations can be performed", "B": "Sorting a database permanently", "C": "Deleting groups", "D": "Creating tables"}
    },
    {
        "skill": "PostgreSQL",
        "level": "intermediate",
        "topic": "Indexes",
        "question": "What is a database index mainly used for?",
        "correct_answer": "A",
        "options": {"A": "Improving the speed of certain queries", "B": "Increasing the size of every row", "C": "Replacing tables", "D": "Encrypting the database"}
    },
    {
        "skill": "PostgreSQL",
        "level": "intermediate",
        "topic": "Transactions",
        "question": "Which SQL command permanently saves changes made during a transaction?",
        "correct_answer": "B",
        "options": {"A": "SAVE", "B": "COMMIT", "C": "APPLY", "D": "ACCEPT"}
    },
    {
        "skill": "PostgreSQL",
        "level": "intermediate",
        "topic": "Foreign Keys",
        "question": "What is a foreign key commonly used for?",
        "correct_answer": "A",
        "options": {"A": "Representing a relationship between tables", "B": "Encrypting a column", "C": "Sorting rows", "D": "Creating a database backup"}
    },
    # POSTGRESQL — ADVANCED
    {
        "skill": "PostgreSQL",
        "level": "advanced",
        "topic": "Transactions",
        "question": "What is the main purpose of a database transaction?",
        "correct_answer": "A",
        "options": {"A": "Group multiple operations into a logical unit of work", "B": "Make every query run faster", "C": "Automatically create indexes", "D": "Replace database tables"}
    },
    {
        "skill": "PostgreSQL",
        "level": "advanced",
        "topic": "Isolation",
        "question": "What does transaction isolation help control?",
        "correct_answer": "A",
        "options": {"A": "How concurrent transactions can see each other's changes", "B": "The physical size of the database", "C": "The number of database columns", "D": "The database password"}
    },
    {
        "skill": "PostgreSQL",
        "level": "advanced",
        "topic": "Query Performance",
        "question": "Which PostgreSQL command can be used to inspect how PostgreSQL plans to execute a query?",
        "correct_answer": "A",
        "options": {"A": "EXPLAIN", "B": "ANALYZE QUERY ONLY", "C": "PLAN SQL", "D": "QUERY DEBUG"}
    },
    {
        "skill": "PostgreSQL",
        "level": "advanced",
        "topic": "CTE",
        "question": "What is a Common Table Expression (CTE) introduced with WITH mainly useful for?",
        "correct_answer": "A",
        "options": {"A": "Defining a temporary named query result within a statement", "B": "Creating a permanent database", "C": "Encrypting a table", "D": "Starting a PostgreSQL server"}
    },
    {
        "skill": "PostgreSQL",
        "level": "advanced",
        "topic": "Window Functions",
        "question": "What is a major characteristic of a SQL window function?",
        "correct_answer": "A",
        "options": {"A": "It can calculate across related rows without collapsing them into one row per group", "B": "It always deletes duplicate rows", "C": "It can only return one row", "D": "It permanently changes the table"}
    }
]


def seed_assessment_questions(db: Session):
    """
    Idempotently seeds all 45 MCQ questions and options into the database.
    """
    for q_data in INITIAL_QUESTIONS:
        existing = db.query(AssessmentQuestion).filter(
            AssessmentQuestion.skill == q_data["skill"],
            AssessmentQuestion.level == q_data["level"],
            AssessmentQuestion.question == q_data["question"]
        ).first()

        if not existing:
            q_obj = AssessmentQuestion(
                skill=q_data["skill"],
                level=q_data["level"],
                topic=q_data.get("topic"),
                question=q_data["question"],
                correct_answer=q_data["correct_answer"],
                is_active=True
            )
            db.add(q_obj)
            db.flush()  # to get q_obj.id

            for opt_key, opt_text in q_data["options"].items():
                opt_obj = QuestionOption(
                    question_id=q_obj.id,
                    option_key=opt_key,
                    option_text=opt_text
                )
                db.add(opt_obj)

    db.commit()
