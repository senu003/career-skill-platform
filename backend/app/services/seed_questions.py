from sqlalchemy.orm import Session
from app.models import AssessmentQuestion, QuestionOption

INITIAL_QUESTIONS = [
    # JAVASCRIPT — BASIC (10 questions)
    {
        "skill": "JavaScript", "level": "basic", "topic": "Variables",
        "question": "Which keyword is used to declare a variable that cannot be reassigned?",
        "correct_answer": "C", "options": {"A": "var", "B": "let", "C": "const", "D": "static"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Data Types",
        "question": "Which of the following is a JavaScript primitive data type?",
        "correct_answer": "C", "options": {"A": "Array", "B": "Object", "C": "String", "D": "Function"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Arrays",
        "question": "Which method adds an element to the end of a JavaScript array?",
        "correct_answer": "A", "options": {"A": "push()", "B": "pop()", "C": "shift()", "D": "unshift()"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Functions",
        "question": "Which syntax correctly defines a JavaScript function?",
        "correct_answer": "A", "options": {"A": "function greet() { }", "B": "def greet() { }", "C": "func greet() { }", "D": "function: greet() { }"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Conditions",
        "question": "Which operator checks both value and type equality?",
        "correct_answer": "C", "options": {"A": "=", "B": "==", "C": "===", "D": "!="}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Strings",
        "question": "Which property returns the length of a string in JavaScript?",
        "correct_answer": "A", "options": {"A": "length", "B": "size", "C": "count", "D": "index"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Loops",
        "question": "Which loop statement executes code as long as a specified condition evaluates to true?",
        "correct_answer": "B", "options": {"A": "repeat", "B": "while", "C": "during", "D": "loop"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Booleans",
        "question": "What is the boolean result of Boolean('') in JavaScript?",
        "correct_answer": "B", "options": {"A": "true", "B": "false", "C": "undefined", "D": "null"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Math",
        "question": "Which Math function rounds a number up to the next largest integer?",
        "correct_answer": "B", "options": {"A": "Math.floor()", "B": "Math.ceil()", "C": "Math.round()", "D": "Math.abs()"}
    },
    {
        "skill": "JavaScript", "level": "basic", "topic": "Console",
        "question": "Which method prints output to the developer console?",
        "correct_answer": "A", "options": {"A": "console.log()", "B": "print()", "C": "system.out()", "D": "echo()"}
    },

    # JAVASCRIPT — INTERMEDIATE (10 questions)
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Array Methods",
        "question": "What does the map() method normally return?",
        "correct_answer": "B", "options": {"A": "The original array only", "B": "A new array", "C": "A boolean", "D": "A string"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Array Methods",
        "question": "What does filter() return?",
        "correct_answer": "A", "options": {"A": "A new array containing elements that satisfy a condition", "B": "The first element matching a condition", "C": "A boolean", "D": "The number of matching elements"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Async JavaScript",
        "question": "What does an async function return?",
        "correct_answer": "C", "options": {"A": "A string", "B": "An array", "C": "A Promise", "D": "A callback"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Promises",
        "question": "Which keyword is normally used to wait for a Promise inside an async function?",
        "correct_answer": "B", "options": {"A": "wait", "B": "await", "C": "pause", "D": "async"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Scope",
        "question": "What is a major difference between let and var?",
        "correct_answer": "A", "options": {"A": "let is block-scoped while var is function-scoped", "B": "var is block-scoped while let is function-scoped", "C": "They always have exactly the same scope", "D": "let cannot store numbers"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Objects",
        "question": "Which method returns an array of a given object's own enumerable property names?",
        "correct_answer": "A", "options": {"A": "Object.keys()", "B": "Object.values()", "C": "Object.entries()", "D": "Object.properties()"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Spread Operator",
        "question": "What does the spread operator (...) do when creating a new array from an existing one?",
        "correct_answer": "A", "options": {"A": "Unpacks elements into the new array", "B": "Deletes duplicate elements", "C": "Reverses the element order", "D": "Converts items to strings"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Array Search",
        "question": "Which method checks if at least one element in an array satisfies a testing function?",
        "correct_answer": "B", "options": {"A": "every()", "B": "some()", "C": "includes()", "D": "findIndex()"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Template Literals",
        "question": "Which enclosing character is used for JavaScript template literals?",
        "correct_answer": "C", "options": {"A": "Single quotes ('')", "B": "Double quotes (\"\")", "C": "Backticks (``)", "D": "Angle brackets (<>)"}
    },
    {
        "skill": "JavaScript", "level": "intermediate", "topic": "Type Coercion",
        "question": "What is the return value of typeof NaN in JavaScript?",
        "correct_answer": "A", "options": {"A": "'number'", "B": "'nan'", "C": "'undefined'", "D": "'object'"}
    },

    # JAVASCRIPT — ADVANCED (10 questions)
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Closures",
        "question": "What is a closure in JavaScript?",
        "correct_answer": "A", "options": {"A": "A function that remembers variables from its outer scope", "B": "A function that always returns an object", "C": "A method used to close browser windows", "D": "A special type of loop"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Event Loop",
        "question": "What is the main purpose of the JavaScript event loop?",
        "correct_answer": "B", "options": {"A": "Compile JavaScript into machine code", "B": "Manage asynchronous callbacks and execution", "C": "Create HTML elements", "D": "Store variables permanently"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Promises",
        "question": "Which Promise method runs when a Promise is rejected?",
        "correct_answer": "C", "options": {"A": "then()", "B": "resolve()", "C": "catch()", "D": "finallyOnly()"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Destructuring",
        "question": "What does const { name, age } = user; do?",
        "correct_answer": "B", "options": {"A": "Creates a new user object", "B": "Extracts name and age properties from user", "C": "Deletes name and age", "D": "Converts user to an array"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Functional Programming",
        "question": "What is a key difference between reduce() and map()?",
        "correct_answer": "A", "options": {"A": "reduce() can transform an array into a single accumulated value", "B": "map() can only work with numbers", "C": "reduce() cannot use functions", "D": "They always produce exactly the same result"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Prototypes",
        "question": "What is at the top of the prototype inheritance chain in JavaScript?",
        "correct_answer": "B", "options": {"A": "Function.prototype", "B": "Object.prototype", "C": "Array.prototype", "D": "null"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Generators",
        "question": "Which keyword pauses and resumes execution inside a generator function?",
        "correct_answer": "A", "options": {"A": "yield", "B": "pause", "C": "await", "D": "defer"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "WeakMap",
        "question": "What is a key property of keys stored in a JavaScript WeakMap?",
        "correct_answer": "C", "options": {"A": "Keys must be primitive strings", "B": "Keys can be iterated using for...of", "C": "Keys must be objects and are weakly held", "D": "Keys are permanently kept in memory"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Modules",
        "question": "Which export keyword allows exporting multiple named variables from a module?",
        "correct_answer": "A", "options": {"A": "export", "B": "export default", "C": "module.exports", "D": "package.export"}
    },
    {
        "skill": "JavaScript", "level": "advanced", "topic": "Async Handling",
        "question": "What happens if a Promise passed to await rejects inside a try block?",
        "correct_answer": "B", "options": {"A": "The program silently ignores it", "B": "Execution moves directly to the catch block", "C": "The server restarts", "D": "It converts into undefined"}
    },

    # REACT — BASIC (10 questions)
    {
        "skill": "React", "level": "basic", "topic": "Components",
        "question": "What is a React component?",
        "correct_answer": "A", "options": {"A": "A reusable UI building block", "B": "A database table", "C": "A CSS file", "D": "A backend server"}
    },
    {
        "skill": "React", "level": "basic", "topic": "JSX",
        "question": "What is JSX mainly used for in React?",
        "correct_answer": "B", "options": {"A": "Writing SQL queries", "B": "Describing UI structure using JavaScript-like syntax", "C": "Creating database connections", "D": "Managing HTTP servers"}
    },
    {
        "skill": "React", "level": "basic", "topic": "Props",
        "question": "What are props mainly used for?",
        "correct_answer": "A", "options": {"A": "Passing data from a parent component to a child component", "B": "Storing data permanently in a database", "C": "Styling only", "D": "Creating API endpoints"}
    },
    {
        "skill": "React", "level": "basic", "topic": "State",
        "question": "Which React Hook is commonly used to manage component state?",
        "correct_answer": "A", "options": {"A": "useState", "B": "useRoute", "C": "useServer", "D": "useDatabase"}
    },
    {
        "skill": "React", "level": "basic", "topic": "Lists",
        "question": "Why should React list items usually have a key prop?",
        "correct_answer": "A", "options": {"A": "To help React identify list items efficiently", "B": "To encrypt the list", "C": "To make CSS work", "D": "To connect the list to a database"}
    },
    {
        "skill": "React", "level": "basic", "topic": "Virtual DOM",
        "question": "What is the main advantage of React's Virtual DOM?",
        "correct_answer": "A", "options": {"A": "Minimizes direct DOM manipulation to improve performance", "B": "Connects directly to SQL", "C": "Styles components automatically", "D": "Deletes unused files"}
    },
    {
        "skill": "React", "level": "basic", "topic": "JSX Expressions",
        "question": "How do you embed a JavaScript expression inside JSX markup?",
        "correct_answer": "B", "options": {"A": "Inside quotes \"\"", "B": "Inside curly braces {}", "C": "Inside square brackets []", "D": "Inside parenthetical ()"}
    },
    {
        "skill": "React", "level": "basic", "topic": "Event Names",
        "question": "How are event names formatted in React JSX elements?",
        "correct_answer": "B", "options": {"A": "lowercase (onclick)", "B": "camelCase (onClick)", "C": "UPPERCASE (ONCLICK)", "D": "kebab-case (on-click)"}
    },
    {
        "skill": "React", "level": "basic", "topic": "Fragments",
        "question": "Which syntax creates a lightweight React Fragment wrapper?",
        "correct_answer": "A", "options": {"A": "<></>", "B": "<div fragment>", "C": "<block></block>", "D": "<wrapper></wrapper>"}
    },
    {
        "skill": "React", "level": "basic", "topic": "Immutability",
        "question": "Why should you avoid directly mutating state variables in React?",
        "correct_answer": "B", "options": {"A": "JavaScript throws a syntax error", "B": "React cannot detect the mutation to trigger a re-render", "C": "The database becomes corrupt", "D": "Styles stop working"}
    },

    # REACT — INTERMEDIATE (10 questions)
    {
        "skill": "React", "level": "intermediate", "topic": "useEffect",
        "question": "What is useEffect() commonly used for?",
        "correct_answer": "A", "options": {"A": "Handling side effects such as API calls", "B": "Creating CSS classes", "C": "Defining database tables", "D": "Replacing JSX"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "State Updates",
        "question": "What is the recommended way to update state based on its previous value?",
        "correct_answer": "B", "options": {"A": "Directly modify the state variable", "B": "Use the functional form of the state setter", "C": "Refresh the browser", "D": "Modify the DOM directly"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "Controlled Components",
        "question": "What is a controlled input in React?",
        "correct_answer": "A", "options": {"A": "An input whose value is controlled by React state", "B": "An input controlled only by CSS", "C": "An input that cannot be edited", "D": "An input stored directly in PostgreSQL"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "Component Communication",
        "question": "How can a child component commonly communicate an event to its parent?",
        "correct_answer": "A", "options": {"A": "By calling a callback function passed through props", "B": "By directly changing the parent's state variable", "C": "By changing the database", "D": "By restarting React"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "Conditional Rendering",
        "question": "Which is a common way to conditionally render JSX?",
        "correct_answer": "A", "options": {"A": "Using a JavaScript condition such as a ternary operator", "B": "Using SQL", "C": "Using Python decorators", "D": "Using Docker"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "useRef",
        "question": "What is a common use case for the useRef Hook?",
        "correct_answer": "B", "options": {"A": "Triggering a re-render on every mutation", "B": "Accessing DOM nodes or storing mutable values without re-rendering", "C": "Styling components", "D": "Fetching backend routes"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "Context API",
        "question": "What primary problem does the React Context API solve?",
        "correct_answer": "A", "options": {"A": "Avoiding deep prop drilling across components", "B": "Compiling CSS", "C": "Writing SQL joins", "D": "Parsing PDF files"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "Custom Hooks",
        "question": "What naming rule must custom React Hooks follow?",
        "correct_answer": "B", "options": {"A": "Must end with 'Hook'", "B": "Must start with the prefix 'use'", "C": "Must be written in uppercase", "D": "Must start with 'get'"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "useReducer",
        "question": "When is useReducer often preferred over useState?",
        "correct_answer": "A", "options": {"A": "When state logic is complex with multiple sub-values", "B": "When rendering static text", "C": "When writing CSS grid", "D": "When making simple GET requests"}
    },
    {
        "skill": "React", "level": "intermediate", "topic": "Lifting State Up",
        "question": "What does 'lifting state up' mean in React design?",
        "correct_answer": "A", "options": {"A": "Moving state to the closest common parent component", "B": "Uploading state to cloud storage", "C": "Converting state to local storage", "D": "Deleting component state"}
    },

    # REACT — ADVANCED (10 questions)
    {
        "skill": "React", "level": "advanced", "topic": "Performance",
        "question": "What is useMemo() primarily intended to do?",
        "correct_answer": "A", "options": {"A": "Memoize a calculated value", "B": "Make API requests", "C": "Create a new component", "D": "Store data in PostgreSQL"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Performance",
        "question": "What is useCallback() primarily used for?",
        "correct_answer": "A", "options": {"A": "Memoizing a function reference", "B": "Creating database tables", "C": "Fetching images", "D": "Replacing useState"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Rendering",
        "question": "Why can changing a component's state cause it to render again?",
        "correct_answer": "A", "options": {"A": "React needs to update the UI based on the new state", "B": "The browser must restart", "C": "PostgreSQL automatically sends a request", "D": "JavaScript variables cannot change"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "State Architecture",
        "question": "When is a global state management solution particularly useful?",
        "correct_answer": "A", "options": {"A": "When state needs to be shared across many unrelated components", "B": "When rendering one static paragraph", "C": "When writing CSS", "D": "When creating a PostgreSQL table"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Hooks",
        "question": "What is an important rule when using React Hooks?",
        "correct_answer": "A", "options": {"A": "Hooks should generally be called at the top level of React components or custom Hooks", "B": "Hooks should always be called inside loops", "C": "Hooks can only be called inside event handlers", "D": "Hooks should only be called from CSS"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "HOC",
        "question": "What is a Higher-Order Component (HOC) in React pattern design?",
        "correct_answer": "B", "options": {"A": "A component rendered at the top of the HTML page", "B": "A function that takes a component and returns a new component", "C": "A database model", "D": "A CSS framework"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Code Splitting",
        "question": "Which pair is commonly used for component code splitting in React?",
        "correct_answer": "A", "options": {"A": "React.lazy() and <Suspense>", "B": "useEffect and useState", "C": "useMemo and useCallback", "D": "fetch and async"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Error Boundaries",
        "question": "Which lifecycle method can catch JavaScript errors in a child component tree?",
        "correct_answer": "C", "options": {"A": "componentDidMount", "B": "render", "C": "componentDidCatch", "D": "shouldComponentUpdate"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Concurrent Mode",
        "question": "What is the purpose of useTransition() in React 18?",
        "correct_answer": "A", "options": {"A": "Mark state updates as non-urgent transitions", "B": "Animate CSS elements", "C": "Connect to database transactions", "D": "Download static files"}
    },
    {
        "skill": "React", "level": "advanced", "topic": "Profiler",
        "question": "What is the React <Profiler> component used for?",
        "correct_answer": "B", "options": {"A": "Creating user logins", "B": "Measuring rendering performance and cost of a React sub-tree", "C": "Writing SQL schemas", "D": "Setting up server routes"}
    },

    # POSTGRESQL — BASIC (10 questions)
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "SELECT",
        "question": "Which SQL statement retrieves data from a table?",
        "correct_answer": "B", "options": {"A": "GET", "B": "SELECT", "C": "FETCHTABLE", "D": "READ"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "INSERT",
        "question": "Which SQL command adds a new row to a table?",
        "correct_answer": "B", "options": {"A": "ADD", "B": "INSERT", "C": "CREATE ROW", "D": "APPEND TABLE"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "Primary Keys",
        "question": "What is the main purpose of a primary key?",
        "correct_answer": "A", "options": {"A": "Uniquely identify rows in a table", "B": "Store passwords", "C": "Sort every column automatically", "D": "Create a backup"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "Filtering",
        "question": "Which SQL clause is used to filter rows?",
        "correct_answer": "A", "options": {"A": "WHERE", "B": "FILTER", "C": "SELECTED", "D": "HAVING ONLY"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "Database Structure",
        "question": "What is a table in a relational database?",
        "correct_answer": "A", "options": {"A": "A collection of rows and columns", "B": "A programming function", "C": "A server", "D": "A network connection"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "UPDATE",
        "question": "Which SQL command modifies existing records in a table?",
        "correct_answer": "A", "options": {"A": "UPDATE", "B": "MODIFY", "C": "CHANGE", "D": "SET DATA"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "DELETE",
        "question": "Which SQL statement removes existing rows from a table?",
        "correct_answer": "C", "options": {"A": "REMOVE", "B": "TRUNCATE ONLY", "C": "DELETE FROM", "D": "DISCARD"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "Sorting",
        "question": "Which clause is used to sort the result set of a query?",
        "correct_answer": "B", "options": {"A": "GROUP BY", "B": "ORDER BY", "C": "SORT WITH", "D": "ARRANGE BY"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "NULLs",
        "question": "How do you correctly check for NULL values in a WHERE clause?",
        "correct_answer": "B", "options": {"A": "column = NULL", "B": "column IS NULL", "C": "column == NULL", "D": "column EQUALS NULL"}
    },
    {
        "skill": "PostgreSQL", "level": "basic", "topic": "DDL",
        "question": "Which statement creates a new relational table?",
        "correct_answer": "A", "options": {"A": "CREATE TABLE", "B": "MAKE TABLE", "C": "NEW TABLE", "D": "BUILD TABLE"}
    },

    # POSTGRESQL — INTERMEDIATE (10 questions)
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "JOIN",
        "question": "What is the purpose of a JOIN?",
        "correct_answer": "A", "options": {"A": "Combine related data from multiple tables", "B": "Delete duplicate databases", "C": "Create a server", "D": "Encrypt data"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "GROUP BY",
        "question": "What is GROUP BY commonly used for?",
        "correct_answer": "A", "options": {"A": "Grouping rows so aggregate calculations can be performed", "B": "Sorting a database permanently", "C": "Deleting groups", "D": "Creating tables"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "Indexes",
        "question": "What is a database index mainly used for?",
        "correct_answer": "A", "options": {"A": "Improving the speed of certain queries", "B": "Increasing the size of every row", "C": "Replacing tables", "D": "Encrypting the database"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "Transactions",
        "question": "Which SQL command permanently saves changes made during a transaction?",
        "correct_answer": "B", "options": {"A": "SAVE", "B": "COMMIT", "C": "APPLY", "D": "ACCEPT"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "Foreign Keys",
        "question": "What is a foreign key commonly used for?",
        "correct_answer": "A", "options": {"A": "Representing a relationship between tables", "B": "Encrypting a column", "C": "Sorting rows", "D": "Creating a database backup"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "HAVING",
        "question": "What is the key difference between WHERE and HAVING?",
        "correct_answer": "A", "options": {"A": "WHERE filters rows before grouping; HAVING filters aggregated groups", "B": "HAVING works on single rows while WHERE works on groups", "C": "They are exact synonyms", "D": "HAVING can only be used with SELECT *"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "UNION",
        "question": "What does the UNION operator do?",
        "correct_answer": "B", "options": {"A": "Multiplies row values", "B": "Combines result sets of two queries and removes duplicates", "C": "Deletes matching rows", "D": "Joins columns horizontally"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "Coalesce",
        "question": "What does COALESCE(val1, val2, val3) return?",
        "correct_answer": "A", "options": {"A": "The first non-null argument", "B": "The sum of all arguments", "C": "A count of nulls", "D": "True if any value is null"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "ALTER TABLE",
        "question": "Which SQL clause adds a column to an existing table?",
        "correct_answer": "A", "options": {"A": "ALTER TABLE table_name ADD COLUMN column_name type;", "B": "UPDATE TABLE table_name INSERT COLUMN;", "C": "MODIFY TABLE table_name APPEND;", "D": "CHANGE TABLE table_name NEW COLUMN;"}
    },
    {
        "skill": "PostgreSQL", "level": "intermediate", "topic": "Subqueries",
        "question": "What is a correlated subquery?",
        "correct_answer": "B", "options": {"A": "A subquery that runs independently of the outer query", "B": "A subquery that evaluates once per row using outer query columns", "C": "A query that creates a view", "D": "A query without a WHERE clause"}
    },

    # POSTGRESQL — ADVANCED (10 questions)
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Transactions",
        "question": "What is the main purpose of a database transaction?",
        "correct_answer": "A", "options": {"A": "Group multiple operations into a logical unit of work", "B": "Make every query run faster", "C": "Automatically create indexes", "D": "Replace database tables"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Isolation",
        "question": "What does transaction isolation help control?",
        "correct_answer": "A", "options": {"A": "How concurrent transactions can see each other's changes", "B": "The physical size of the database", "C": "The number of database columns", "D": "The database password"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Query Performance",
        "question": "Which PostgreSQL command can be used to inspect how PostgreSQL plans to execute a query?",
        "correct_answer": "A", "options": {"A": "EXPLAIN", "B": "ANALYZE QUERY ONLY", "C": "PLAN SQL", "D": "QUERY DEBUG"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "CTE",
        "question": "What is a Common Table Expression (CTE) introduced with WITH mainly useful for?",
        "correct_answer": "A", "options": {"A": "Defining a temporary named query result within a statement", "B": "Creating a permanent database", "C": "Encrypting a table", "D": "Starting a PostgreSQL server"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Window Functions",
        "question": "What is a major characteristic of a SQL window function?",
        "correct_answer": "A", "options": {"A": "It can calculate across related rows without collapsing them into one row per group", "B": "It always deletes duplicate rows", "C": "It can only return one row", "D": "It permanently changes the table"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "MVCC",
        "question": "What does MVCC stand for in PostgreSQL architecture?",
        "correct_answer": "A", "options": {"A": "Multi-Version Concurrency Control", "B": "Maximum Variable Capacity Calculation", "C": "Multi-Vector Compression Control", "D": "Memory Virtual Communication Channel"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Indexes",
        "question": "Which index type is the default index structure in PostgreSQL?",
        "correct_answer": "B", "options": {"A": "Hash", "B": "B-tree", "C": "GIN", "D": "BRIN"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Vacuum",
        "question": "What is the primary function of VACUUM in PostgreSQL?",
        "correct_answer": "A", "options": {"A": "Reclaim storage occupied by dead tuples", "B": "Delete user accounts", "C": "Create index backups", "D": "Compress log files"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "Partitioning",
        "question": "What is table partitioning in PostgreSQL?",
        "correct_answer": "A", "options": {"A": "Splitting one large logical table into smaller physical pieces", "B": "Encrypting passwords across servers", "C": "Merging two databases into one", "D": "Converting SQL to JSON"}
    },
    {
        "skill": "PostgreSQL", "level": "advanced", "topic": "WAL",
        "question": "What does WAL stand for in PostgreSQL durability architecture?",
        "correct_answer": "B", "options": {"A": "Weighted Allocation List", "B": "Write-Ahead Logging", "C": "Wide Access Layer", "D": "Work Automation Log"}
    }
]


def seed_assessment_questions(db: Session):
    """
    Idempotently seeds MCQ questions and options into the database.
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
                question_type="MCQ",
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
