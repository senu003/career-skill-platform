"""
Enriches seeded assessment questions with clear explanations, misconceptions, and interview tips.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import AssessmentQuestion

# Topic-level and question-specific explanations, misconceptions, and interview tips
EXPLANATIONS_DATA: Dict[str, Dict[str, str]] = {
    # JavaScript
    "Which keyword is used to declare a variable that cannot be reassigned?": {
        "explanation": "'const' creates an immutable binding. The variable identifier cannot be reassigned, although object properties bound to it can still be mutated.",
        "misconception": "Candidates often assume 'const' makes objects completely deeply immutable (frozen). In reality, it only prevents reassignment of the variable reference.",
        "interview_tip": "When asked about variable declarations, explain the temporal dead zone (TDZ) for 'let' and 'const' vs hoisting behavior with 'var'."
    },
    "Which of the following is a JavaScript primitive data type?": {
        "explanation": "String is one of JavaScript's 7 primitive types (string, number, bigint, boolean, symbol, undefined, null). Array, Object, and Function are reference types.",
        "misconception": "Thinking Arrays or Functions are separate primitive types. In JavaScript, arrays and functions are specialized objects with Object in their prototype chain.",
        "interview_tip": "Clearly distinguish between primitives (passed by value, stored on the stack) and objects (passed by reference, stored on the heap)."
    },
    "Which method adds an element to the end of a JavaScript array?": {
        "explanation": "array.push() appends one or more elements to the end of an array and returns the new length of the array.",
        "misconception": "Confusing push() with unshift(), which prepends elements to the beginning of the array with O(n) reindexing overhead.",
        "interview_tip": "Mention time complexity: push/pop operate in O(1) amortized time, whereas shift/unshift require O(n) because all subsequent elements must be re-indexed."
    },
    "Which syntax correctly defines a JavaScript function?": {
        "explanation": "JavaScript uses the 'function' keyword: 'function greet() { }', or arrow syntax: 'const greet = () => { }'.",
        "misconception": "Using 'def' (Python syntax) or 'func' (Go/Swift syntax) in JavaScript code.",
        "interview_tip": "Be prepared to explain the difference in 'this' binding between regular function declarations and ES6 arrow functions."
    },
    "Which operator checks both value and type equality?": {
        "explanation": "The strict equality operator '===' checks both value and data type without performing implicit type coercion.",
        "misconception": "Relying on loose equality '==' which coerces types implicitly (e.g., '0 == false' evaluates to true), creating subtle logic bugs.",
        "interview_tip": "Always state that '===' is the default best practice in modern JavaScript to eliminate coercion surprises."
    },
    "Which property returns the length of a string in JavaScript?": {
        "explanation": "'length' is a built-in property on String instances that returns the number of UTF-16 code units in the string.",
        "misconception": "Calling .length() as a method like in Java. In JavaScript, length is a property accessor, not a function.",
        "interview_tip": "Note that surrogate pairs (like certain emojis or rare Unicode characters) can count as 2 UTF-16 units."
    },
    "Which loop statement executes code as long as a specified condition evaluates to true?": {
        "explanation": "A 'while' loop evaluates its condition before executing the block, looping as long as the expression remains truthy.",
        "misconception": "Confusing 'while' with 'do...while'. A 'while' loop may execute zero times if the condition is initially false.",
        "interview_tip": "Discuss termination conditions and avoiding infinite loops when mutating loop state variables."
    },
    "What is the boolean result of Boolean('') in JavaScript?": {
        "explanation": "An empty string '' is one of JavaScript's falsy values (along with false, 0, -0, 0n, null, undefined, and NaN).",
        "misconception": "Assuming any string object is truthy. Only non-empty strings are truthy; '' evaluates to false.",
        "interview_tip": "List the complete set of falsy values in JavaScript to demonstrate foundational fluency."
    },
    "Which Math function rounds a number up to the next largest integer?": {
        "explanation": "Math.ceil() (ceiling) always rounds a floating-point number upwards to the nearest integer.",
        "misconception": "Mixing up Math.ceil() with Math.floor() (which rounds down) or Math.round() (which rounds to nearest .5).",
        "interview_tip": "Useful when implementing pagination calculation: Math.ceil(totalItems / itemsPerPage)."
    },
    "Which method prints output to the developer console?": {
        "explanation": "console.log() writes informational messages to the browser developer tools or Node.js stdout.",
        "misconception": "Thinking print() works in JavaScript — print() in browsers triggers the browser's Print dialog.",
        "interview_tip": "Mention other console methods like console.error(), console.warn(), and console.table() for structured debugging."
    },
    "What does the map() method normally return?": {
        "explanation": "Array.prototype.map() creates a brand new array populated with the results of calling the provided callback on every element.",
        "misconception": "Believing map() mutates the original array or that it returns a boolean. It returns a new array of identical length.",
        "interview_tip": "Emphasize immutability in functional programming and React state updates — map() produces a new reference."
    },
    "What does filter() return?": {
        "explanation": "Array.prototype.filter() returns a new array containing all elements that pass the predicate test (where callback returns truthy).",
        "misconception": "Confusing filter() with find(). filter() returns an array of all matches; find() returns the single first matching item.",
        "interview_tip": "Explain that filter() does not mutate the source array and returns an empty array [] if no items match."
    },
    "What does an async function return?": {
        "explanation": "An async function always implicitly wraps its return value in a Promise, resolving to the returned value.",
        "misconception": "Thinking an async function returns the synchronous un-wrapped value directly.",
        "interview_tip": "Explain that 'return 42' inside an async function is syntactic sugar for 'return Promise.resolve(42)'."
    },
    "Which method is called on a Promise to handle fulfilled outcomes?": {
        "explanation": "Promise.prototype.then() takes a callback that executes when the promise resolves successfully.",
        "misconception": "Assuming .catch() handles successes. .catch() is strictly for rejections and thrown exceptions.",
        "interview_tip": "Compare promise chaining with modern async/await and try/catch blocks for readable asynchronous flow control."
    },
    "What is the lexical scope of a variable declared with 'let'?": {
        "explanation": "'let' is block-scoped, meaning it is accessible only within the nearest enclosing pair of curly braces {}.",
        "misconception": "Believing 'let' is function-scoped like 'var'. 'var' ignores block boundaries like 'if' and 'for' blocks.",
        "interview_tip": "Highlight how block scoping in 'for' loops solves the classic closure bug with asynchronous callbacks inside loops."
    },
    "What does a closure in JavaScript retain access to?": {
        "explanation": "A closure retains access to the lexical environment (outer scope variables) in which it was declared, even after that outer function has returned.",
        "misconception": "Thinking closures make static copies of variables. Closures hold live references to outer variables.",
        "interview_tip": "Provide real-world use cases: data privacy/encapsulation, factory functions, currying, and memoization."
    },
    "How does the JavaScript Event Loop handle asynchronous callbacks?": {
        "explanation": "Synchronous code executes on the Call Stack. Asynchronous callbacks are queued in Task/Microtask queues and pushed onto the Call Stack only when it is completely empty.",
        "misconception": "Believing JavaScript is multi-threaded because of setTimeout. JavaScript has a single-threaded runtime driven by the event loop.",
        "interview_tip": "Differentiate between Microtasks (Promises, queueMicrotask) which run first, and Macrotasks (setTimeout, setInterval)."
    },

    # React
    "What is the primary purpose of a React component?": {
        "explanation": "React components are reusable, independent pieces of UI that accept inputs (props) and return JSX describing what should appear on screen.",
        "misconception": "Thinking React components directly mutate the real browser DOM. Components describe a virtual DOM node tree.",
        "interview_tip": "Explain component composition over inheritance as one of React's core design tenets."
    },
    "What is JSX in React?": {
        "explanation": "JSX is a syntax extension for JavaScript that looks similar to HTML, which compiles down to React.createElement() function calls.",
        "misconception": "Believing JSX is HTML parsed by the browser. Browsers cannot read JSX directly; it must be transpiled by Babel or SWC.",
        "interview_tip": "Mention that JSX allows the full expressive power of JavaScript inside markup expressions."
    },
    "How are properties passed into child components in React?": {
        "explanation": "Props (properties) are passed downward from parent to child via attributes on JSX tags, establishing unidirectional data flow.",
        "misconception": "Attempting to mutate props inside a child component. Props are read-only / immutable to the receiving component.",
        "interview_tip": "Describe unidirectional data flow and how state lifting allows child components to communicate changes back up."
    },
    "Which hook manages local component state in functional components?": {
        "explanation": "useState() declares a state variable and a setter function, triggering a re-render when the setter is called with a new value.",
        "misconception": "Directly mutating state variables (e.g., state.count = 5) instead of calling the setter. Direct mutation bypasses re-rendering.",
        "interview_tip": "Mention functional state updates: setState(prev => prev + 1) when new state depends on previous state."
    },
    "Why must list items in React have a unique 'key' prop?": {
        "explanation": "Keys give elements a stable identity across renders, allowing React's reconciliation algorithm to efficiently determine which items were added, removed, or reordered.",
        "misconception": "Using array index as a key for dynamic lists. If list items are sorted, deleted, or inserted, index keys cause state bugs and extra renders.",
        "interview_tip": "Explain that stable IDs from database records should always be preferred over array indices for dynamic lists."
    },
    "When does useEffect execute if its dependency array is empty []?": {
        "explanation": "With an empty dependency array [], the effect executes once after the initial mount, and its cleanup function runs on unmount.",
        "misconception": "Believing [] means the effect runs on every render. No array = every render; [] = mount only; [dep] = when dep changes.",
        "interview_tip": "Discuss cleanup functions for canceling subscriptions, clearing timers, or aborting Fetch requests."
    },
    "What is the difference between controlled and uncontrolled components in React?": {
        "explanation": "In controlled components, form data is handled by React component state. In uncontrolled components, form data is handled directly by the DOM itself via refs.",
        "misconception": "Assuming uncontrolled components are deprecated. Uncontrolled components with useRef are valid for simple inputs or file uploads.",
        "interview_tip": "Recommend controlled components for immediate validation, dynamic form fields, and disabling submit buttons."
    },
    "What does useRef return, and what is its primary characteristic?": {
        "explanation": "useRef returns a mutable ref object with a .current property. Mutating .current does NOT trigger a component re-render.",
        "misconception": "Using state when a value doesn't affect the rendered UI. If a value change shouldn't trigger re-render, use useRef.",
        "interview_tip": "Two primary use cases: holding direct DOM references (e.g. focusing an input) and storing mutable instance variables across renders."
    },

    # Python
    "Which data structure in Python is mutable and ordered?": {
        "explanation": "Python lists are mutable (items can be appended, modified, removed) and ordered sequences of elements.",
        "misconception": "Confusing lists with tuples. Tuples are immutable; lists are mutable.",
        "interview_tip": "Mention time complexity: list index access is O(1), appending is amortized O(1), but inserting/deleting at the beginning is O(n)."
    },
    "What is the difference between '==' and 'is' in Python?": {
        "explanation": "'==' checks for value equality (calls __eq__), while 'is' checks for identity (whether both variables point to the exact same memory location / id).",
        "misconception": "Using 'is' for string or integer value comparisons. Small integers and interned strings can fool tests, but 'is' is only for identity.",
        "interview_tip": "State that 'is' is primarily used to check singletons like 'x is None' or 'x is True'."
    },
    "What is a Python generator and how does it yield values?": {
        "explanation": "A generator is a function containing the 'yield' statement that returns an iterator object, producing values lazily on-demand without loading the entire sequence into memory.",
        "misconception": "Thinking generators compute and store all values in RAM simultaneously like a list comprehension.",
        "interview_tip": "Highlight memory efficiency when processing large datasets, streams, or infinite sequences with generators."
    },
    "What is a decorator in Python?": {
        "explanation": "A decorator is a callable that takes another function as an argument and extends or modifies its behavior without modifying the original source code.",
        "misconception": "Believing decorators change function bytecode. They are syntactic sugar: @dec def f(): pass is equivalent to f = dec(f).",
        "interview_tip": "Mention functools.wraps to preserve original function docstrings, name, and signatures."
    },
    "What is Python's Global Interpreter Lock (GIL)?": {
        "explanation": "The GIL is a mutex in CPython that allows only one native thread to execute Python bytecode at a time, protecting memory management from race conditions.",
        "misconception": "Assuming multi-threading in Python is completely useless. I/O-bound tasks release the GIL during network/disk calls; only CPU-bound tasks are constrained.",
        "interview_tip": "In interviews, explain multiprocessing (bypasses GIL with separate processes) vs threading (good for concurrent I/O)."
    },

    # SQL / PostgreSQL
    "Which clause is used in SQL to filter rows before any groupings are applied?": {
        "explanation": "WHERE filters individual rows before aggregation. HAVING filters grouped rows after the GROUP BY clause has executed.",
        "misconception": "Using WHERE with aggregate functions like WHERE COUNT(*) > 5. Aggregates cannot appear in WHERE clauses; use HAVING.",
        "interview_tip": "Walk through the logical query processing order: FROM -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY."
    },
    "What is the difference between INNER JOIN and LEFT JOIN?": {
        "explanation": "INNER JOIN returns only rows with matching values in both tables. LEFT JOIN returns all rows from the left table and matched rows from the right table (with NULLs for unmatched).",
        "misconception": "Assuming LEFT JOIN filters out unmatched left rows. It always preserves all rows from the left table.",
        "interview_tip": "Mention indexing foreign keys on join columns to prevent sequential scans on large tables."
    },
    "What is a database index and what is its primary trade-off?": {
        "explanation": "An index (commonly B-tree) speeds up data retrieval queries (SELECT) at the cost of additional disk storage and slower write operations (INSERT, UPDATE, DELETE).",
        "misconception": "Thinking indexing every column is good practice. Over-indexing degrades write performance and bloats storage.",
        "interview_tip": "Discuss composite index column ordering (most selective / equality columns first) and EXPLAIN ANALYZE."
    },
    "What does the ACID acronym stand for in database transactions?": {
        "explanation": "Atomicity (all or nothing), Consistency (valid state transitions), Isolation (concurrent transactions don't interfere), and Durability (committed data survives crashes).",
        "misconception": "Assuming all databases provide strict serializable isolation by default. Most default to Read Committed.",
        "interview_tip": "Explain transaction isolation levels: Read Uncommitted, Read Committed, Repeatable Read, and Serializable."
    },

    # Docker
    "What is the difference between a Docker image and a Docker container?": {
        "explanation": "A Docker image is a read-only template with instructions for creating a container. A container is a runnable, isolated instance of an image with a read-write layer.",
        "misconception": "Confusing images and containers as interchangeable terms. Images are immutable packages; containers are running processes.",
        "interview_tip": "Use the OOP analogy: an image is like a Class, while a container is an instantiated Object."
    },
    "What is the purpose of Docker multi-stage builds?": {
        "explanation": "Multi-stage builds allow using multiple FROM statements in a Dockerfile, leaving build tools and intermediate artifacts behind to create minimal, secure production images.",
        "misconception": "Believing you need separate Dockerfiles for building and running. Multi-stage builds combine both in a single file.",
        "interview_tip": "Mention production benefits: reduced image size (e.g. from 1GB to 50MB using Alpine/scratch) and reduced CVE attack surface."
    },
    "How does Docker cache layers efficiently during 'docker build'?": {
        "explanation": "Docker evaluates each Dockerfile instruction in sequence. If the instruction and its inputs (like copied files) have not changed, Docker reuses the cached layer.",
        "misconception": "Copying entire project source code before running package install (e.g. COPY . . before npm install). This invalidates the dependency cache on every code change.",
        "interview_tip": "Always advise copying package manifests first (package.json/requirements.txt), running install, then copying application code."
    }
}


def enrich_questions_in_db(db: Session) -> int:
    """
    Enriches existing questions in the database with explanations,
    misconceptions, and interview tips.
    Returns the count of updated questions.
    """
    updated_count = 0
    questions = db.query(AssessmentQuestion).all()

    for q in questions:
        q_text_clean = q.question.strip()
        matched_data: Optional[Dict[str, str]] = None

        # Check direct question match
        if q_text_clean in EXPLANATIONS_DATA:
            matched_data = EXPLANATIONS_DATA[q_text_clean]
        else:
            # Check partial match
            for key, data in EXPLANATIONS_DATA.items():
                if key.lower() in q_text_clean.lower() or q_text_clean.lower() in key.lower():
                    matched_data = data
                    break

        # Fallback topic-based default if no exact question match
        if not matched_data:
            topic_str = q.topic or q.skill
            matched_data = {
                "explanation": f"The correct answer represents the established standard practice for {topic_str} in {q.skill}.",
                "misconception": f"Common errors in {topic_str} occur when confusing language semantics or framework lifecycle timing.",
                "interview_tip": f"In interviews discussing {topic_str}, articulate the trade-offs and underlying runtime mechanics clearly."
            }

        needs_update = False
        if matched_data.get("explanation") and q.explanation != matched_data["explanation"]:
            q.explanation = matched_data["explanation"]
            needs_update = True
        if matched_data.get("misconception") and q.misconception != matched_data["misconception"]:
            q.misconception = matched_data["misconception"]
            needs_update = True
        if matched_data.get("interview_tip") and q.interview_tip != matched_data["interview_tip"]:
            q.interview_tip = matched_data["interview_tip"]
            needs_update = True

        if needs_update:
            db.add(q)
            updated_count += 1

    db.commit()
    return updated_count
