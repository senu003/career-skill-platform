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
    },

    # PYTHON — BASIC (10 questions)
    {
        "skill": "Python", "level": "basic", "topic": "Functions",
        "question": "Which keyword is used to define a function in Python?",
        "correct_answer": "A", "options": {"A": "def", "B": "func", "C": "function", "D": "define"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Data Types",
        "question": "Which Python built-in data type is mutable and ordered?",
        "correct_answer": "B", "options": {"A": "tuple", "B": "list", "C": "str", "D": "frozenset"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Tuples",
        "question": "How do you define a tuple with a single integer element in Python?",
        "correct_answer": "C", "options": {"A": "(1)", "B": "tuple(1)", "C": "(1,)", "D": "[1]"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Loops",
        "question": "Which statement iterates over items of any sequence in Python?",
        "correct_answer": "A", "options": {"A": "for", "B": "loop", "C": "iterate", "D": "foreach"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Booleans",
        "question": "What is the result of bool([]) in Python?",
        "correct_answer": "B", "options": {"A": "True", "B": "False", "C": "None", "D": "Error"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Strings",
        "question": "Which string method removes whitespace from the start and end of a string?",
        "correct_answer": "A", "options": {"A": "strip()", "B": "trim()", "C": "clean()", "D": "cut()"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Dictionaries",
        "question": "Which method returns all values from a Python dictionary?",
        "correct_answer": "B", "options": {"A": "items()", "B": "values()", "C": "keys()", "D": "get_all()"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Comments",
        "question": "Which symbol is used for single-line comments in Python?",
        "correct_answer": "A", "options": {"A": "#", "B": "//", "C": "/*", "D": "--"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Operators",
        "question": "Which operator performs floor integer division in Python?",
        "correct_answer": "B", "options": {"A": "/", "B": "//", "C": "%", "D": "**"}
    },
    {
        "skill": "Python", "level": "basic", "topic": "Built-ins",
        "question": "Which built-in function returns the number of items in a list or string?",
        "correct_answer": "A", "options": {"A": "len()", "B": "size()", "C": "count()", "D": "length()"}
    },

    # PYTHON — INTERMEDIATE (10 questions)
    {
        "skill": "Python", "level": "intermediate", "topic": "List Comprehensions",
        "question": "What is the primary benefit of list comprehensions in Python?",
        "correct_answer": "A", "options": {"A": "Concise syntax for transforming and filtering sequences", "B": "Compiling Python to C", "C": "Creating global variables", "D": "Deleting duplicate items automatically"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Generators",
        "question": "Which keyword turns a regular Python function into a generator?",
        "correct_answer": "B", "options": {"A": "return", "B": "yield", "C": "gen", "D": "emit"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Decorators",
        "question": "What is a decorator in Python?",
        "correct_answer": "A", "options": {"A": "A function that takes another function and extends its behavior", "B": "A GUI layout widget", "C": "A database schema migration", "D": "A style sheet for terminal printing"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Context Managers",
        "question": "Which statement manages resources safely using the context manager protocol?",
        "correct_answer": "B", "options": {"A": "using", "B": "with", "C": "try_resource", "D": "open_as"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Function Arguments",
        "question": "In a function definition, what does **kwargs collect?",
        "correct_answer": "A", "options": {"A": "Arbitrary keyword arguments as a dictionary", "B": "Positional arguments as a list", "C": "Default arguments as a tuple", "D": "Global environment variables"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Lambdas",
        "question": "What is a lambda function in Python?",
        "correct_answer": "A", "options": {"A": "A small anonymous inline function", "B": "A multithreaded daemon process", "C": "A database trigger", "D": "A class constructor"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "OOP",
        "question": "Which method serves as the initializer when a class instance is created?",
        "correct_answer": "C", "options": {"A": "__new__ only", "B": "__start__", "C": "__init__", "D": "__create__"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Exceptions",
        "question": "Which block always executes in a try/except block regardless of errors?",
        "correct_answer": "B", "options": {"A": "else", "B": "finally", "C": "always", "D": "catch"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Sets",
        "question": "Which set method or operator returns elements present in both set A and set B?",
        "correct_answer": "A", "options": {"A": "intersection (&)", "B": "union (|)", "C": "difference (-)", "D": "symmetric_difference (^)"}
    },
    {
        "skill": "Python", "level": "intermediate", "topic": "Modules",
        "question": "What is the value of __name__ when a Python file is run directly?",
        "correct_answer": "A", "options": {"A": "'__main__'", "B": "'root'", "C": "'__init__'", "D": "'__module__'"}
    },

    # PYTHON — ADVANCED (10 questions)
    {
        "skill": "Python", "level": "advanced", "topic": "GIL",
        "question": "What is the primary role of the Global Interpreter Lock (GIL) in CPython?",
        "correct_answer": "A", "options": {"A": "Synchronizes thread execution so only one thread executes Python bytecode at once", "B": "Encrypts source code in memory", "C": "Accelerates GPU computing", "D": "Prevents file system modifications"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Metaclasses",
        "question": "What is a metaclass in Python?",
        "correct_answer": "B", "options": {"A": "A class with only static methods", "B": "A class whose instances are themselves classes", "C": "A deprecated Python 2 feature", "D": "A database ORM entity"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Asyncio",
        "question": "Which syntax defines a native asynchronous coroutine in Python?",
        "correct_answer": "A", "options": {"A": "async def my_func():", "B": "coroutine def my_func():", "C": "def async my_func():", "D": "spawn def my_func():"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Descriptors",
        "question": "Which methods form the descriptor protocol in Python?",
        "correct_answer": "A", "options": {"A": "__get__, __set__, and __delete__", "B": "__init__, __new__, and __del__", "C": "__enter__ and __exit__", "D": "__iter__ and __next__"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Memory",
        "question": "How does CPython primarily reclaim unreferenced memory?",
        "correct_answer": "B", "options": {"A": "Mark-and-sweep only", "B": "Reference counting supplemented by a cyclic garbage collector", "C": "Manual free() calls", "D": "OS page swapping"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Dunder Methods",
        "question": "What is the goal of implementing __repr__ on a custom class?",
        "correct_answer": "A", "options": {"A": "Provide an unambiguous string representation useful for debugging", "B": "Format text for end users", "C": "Convert the object into binary bytes", "D": "Serialize to JSON automatically"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Optimization",
        "question": "What is the main advantage of defining __slots__ in a Python class?",
        "correct_answer": "A", "options": {"A": "Reduces memory footprint by avoiding an instance __dict__", "B": "Makes all attributes public", "C": "Allows multiple inheritance", "D": "Speeds up disk I/O"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Collections",
        "question": "Which collection provides O(1) appends and pops from both ends?",
        "correct_answer": "B", "options": {"A": "list", "B": "collections.deque", "C": "collections.ChainMap", "D": "collections.defaultdict"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Concurrency",
        "question": "Why is the multiprocessing module preferred over threading for CPU-bound Python tasks?",
        "correct_answer": "A", "options": {"A": "Separate processes bypass the GIL and utilize multiple CPU cores", "B": "Processes share memory automatically without IPC", "C": "Threads use more RAM than processes", "D": "CPython forbids threading for math operations"}
    },
    {
        "skill": "Python", "level": "advanced", "topic": "Weak References",
        "question": "What does Python's weakref module provide?",
        "correct_answer": "B", "options": {"A": "Encrypted pointers to remote databases", "B": "References that do not increase the target object's reference count", "C": "Unsafe memory casting", "D": "Lazy imports"}
    },

    # DOCKER — BASIC (10 questions)
    {
        "skill": "Docker", "level": "basic", "topic": "Containers",
        "question": "What is a Docker container?",
        "correct_answer": "A", "options": {"A": "A lightweight, standalone package containing an application and its dependencies", "B": "A full hardware virtual machine with its own hypervisor", "C": "A physical server", "D": "A database table"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Dockerfile",
        "question": "Which instruction specifies the parent base image in a Dockerfile?",
        "correct_answer": "A", "options": {"A": "FROM", "B": "BASE", "C": "ROOT", "D": "IMAGE"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Build",
        "question": "Which command builds a Docker image tagged 'myapp' from the current directory?",
        "correct_answer": "B", "options": {"A": "docker create myapp .", "B": "docker build -t myapp .", "C": "docker make -tag myapp", "D": "docker compile myapp"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "CLI",
        "question": "Which command lists currently running Docker containers?",
        "correct_answer": "A", "options": {"A": "docker ps", "B": "docker list", "C": "docker show", "D": "docker containers"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Images",
        "question": "What is the relationship between a Docker image and a Docker container?",
        "correct_answer": "A", "options": {"A": "A container is a running instance of an image", "B": "An image is a running instance of a container", "C": "They are exact synonyms", "D": "An image is a virtual disk on AWS"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Registry",
        "question": "Which command pulls an image from a Docker registry without running it?",
        "correct_answer": "B", "options": {"A": "docker fetch", "B": "docker pull", "C": "docker download", "D": "docker clone"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Dockerfile",
        "question": "Which instruction specifies the default executable command when a container runs?",
        "correct_answer": "A", "options": {"A": "CMD", "B": "RUN", "C": "EXECUTE", "D": "START"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "CLI",
        "question": "Which command stops a running container gracefully?",
        "correct_answer": "B", "options": {"A": "docker halt", "B": "docker stop", "C": "docker terminate", "D": "docker pause"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Ports",
        "question": "Which flag in 'docker run' maps host port 8080 to container port 80?",
        "correct_answer": "A", "options": {"A": "-p 8080:80", "B": "--port 80:8080", "C": "-m 8080->80", "D": "-expose 8080"}
    },
    {
        "skill": "Docker", "level": "basic", "topic": "Volumes",
        "question": "What is the primary purpose of a Docker volume?",
        "correct_answer": "A", "options": {"A": "Persist data independently of container lifecycle", "B": "Increase CPU limits", "C": "Encrypt network packets", "D": "Compress image layers"}
    },

    # DOCKER — INTERMEDIATE (10 questions)
    {
        "skill": "Docker", "level": "intermediate", "topic": "Compose",
        "question": "What is Docker Compose primarily used for?",
        "correct_answer": "A", "options": {"A": "Defining and running multi-container Docker applications via YAML", "B": "Compiling C++ programs", "C": "Monitoring disk temperature", "D": "Signing SSL certificates"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Multi-stage",
        "question": "What is a major advantage of multi-stage Docker builds?",
        "correct_answer": "A", "options": {"A": "Minimizing final image size by discarding build-time tools", "B": "Running containers across multiple clouds simultaneously", "C": "Encrypting the source code", "D": "Automatically updating dependencies"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Networking",
        "question": "What is the default network driver for containers on a standalone Docker host?",
        "correct_answer": "B", "options": {"A": "host", "B": "bridge", "C": "overlay", "D": "macvlan"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Dockerignore",
        "question": "What is the primary function of a .dockerignore file?",
        "correct_answer": "A", "options": {"A": "Prevent specified files from being sent to the Docker build context", "B": "Block network traffic to specified ports", "C": "Exclude containers from docker ps", "D": "Ignore error codes during docker run"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "ENV vs ARG",
        "question": "What is the key difference between ARG and ENV instructions?",
        "correct_answer": "A", "options": {"A": "ARG is available during image build only; ENV persists in the running container", "B": "ENV is build-only; ARG persists in container runtime", "C": "ARG is encrypted; ENV is plain text", "D": "They are completely interchangeable"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Volumes",
        "question": "Which command creates a named Docker volume?",
        "correct_answer": "A", "options": {"A": "docker volume create", "B": "docker make volume", "C": "docker disk init", "D": "docker mount new"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Logs",
        "question": "Which command views the standard output logs of a container?",
        "correct_answer": "A", "options": {"A": "docker logs", "B": "docker output", "C": "docker tail-system", "D": "docker read"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Healthcheck",
        "question": "What is the purpose of the HEALTHCHECK instruction in a Dockerfile?",
        "correct_answer": "B", "options": {"A": "Scans image for vulnerabilities", "B": "Configures a command to test if the container is functioning properly", "C": "Monitors host hardware fans", "D": "Checks RAM usage every second"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Exec",
        "question": "Which command opens an interactive shell inside a running container?",
        "correct_answer": "A", "options": {"A": "docker exec -it <container_id> sh", "B": "docker attach --interactive <container_id>", "C": "docker run -it <container_id> sh", "D": "docker shell <container_id>"}
    },
    {
        "skill": "Docker", "level": "intermediate", "topic": "Restart Policy",
        "question": "Which restart policy restarts a container unless it was explicitly stopped by the user?",
        "correct_answer": "C", "options": {"A": "always", "B": "on-failure", "C": "unless-stopped", "D": "no"}
    },

    # DOCKER — ADVANCED (10 questions)
    {
        "skill": "Docker", "level": "advanced", "topic": "Security",
        "question": "Why is it recommended to run containers with a non-root USER?",
        "correct_answer": "A", "options": {"A": "To adhere to least privilege and prevent host compromise in case of container breakout", "B": "Because root users cannot listen on network ports", "C": "Because Docker daemon refuses to build images with root", "D": "To speed up image downloads"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Storage Drivers",
        "question": "Which storage driver is the standard default on modern Linux distributions for Docker?",
        "correct_answer": "B", "options": {"A": "aufs", "B": "overlay2", "C": "vfs", "D": "devicemapper"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Isolation",
        "question": "Which Linux kernel features provide process and resource isolation for Docker containers?",
        "correct_answer": "A", "options": {"A": "Namespaces (isolation) and cgroups (resource limits)", "B": "Hyper-V and VirtualBox", "C": "KVM and QEMU", "D": "Systemd and journald"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Orchestration",
        "question": "What is Docker Swarm mode?",
        "correct_answer": "A", "options": {"A": "Built-in cluster management and container orchestration engine", "B": "A peer-to-peer torrent protocol for images", "C": "A load tester for Docker containers", "D": "A tool to compress Dockerfiles"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Build Context",
        "question": "Why does a large Docker build context negatively impact build performance?",
        "correct_answer": "B", "options": {"A": "It crashes the local operating system", "B": "The entire context is transmitted across the socket to the Docker daemon before building begins", "C": "It invalidates CPU registers", "D": "Docker requires 1GB of swap per build file"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Multi-arch",
        "question": "Which Docker tool enables building multi-platform images (e.g., amd64 and arm64)?",
        "correct_answer": "A", "options": {"A": "Docker Buildx", "B": "Docker Compose", "C": "Docker Machine", "D": "Docker Hub Auto"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Resource Limits",
        "question": "Which flags in 'docker run' restrict container CPU and memory usage?",
        "correct_answer": "A", "options": {"A": "--cpus and --memory", "B": "--max-cpu and --max-ram", "C": "-c and -r", "D": "--cores and --bytes"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Capabilities",
        "question": "What does the '--cap-drop ALL' option do during 'docker run'?",
        "correct_answer": "A", "options": {"A": "Removes all default Linux kernel capabilities for enhanced container sandboxing", "B": "Disables memory limits", "C": "Stops all network interfaces", "D": "Deletes all files in the container on exit"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Secrets",
        "question": "What is the recommended method to pass sensitive credentials to containers in production?",
        "correct_answer": "B", "options": {"A": "Hardcoding them into the Dockerfile", "B": "Using Docker Secrets or dedicated secret management mounts", "C": "Committing them to Git", "D": "Baking them into public image tags"}
    },
    {
        "skill": "Docker", "level": "advanced", "topic": "Layers",
        "question": "How does Docker cache layers efficiently during 'docker build'?",
        "correct_answer": "A", "options": {"A": "If a step's command and inputs haven't changed, Docker reuses previously built cached layers", "B": "It always re-downloads every layer from the registry", "C": "It rebuilds all layers when any single file is modified", "D": "Layers are only cached if they are under 10MB"}
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
