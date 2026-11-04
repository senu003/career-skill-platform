/**
 * Domain-specific technical study concept mappings and interview question generator.
 */

export const TECHNICAL_STUDY_CONCEPTS = {
  javascript: {
    advanced: [
      'Asynchronous Patterns (Promises, Async/Await, Microtasks)',
      'Event Loop & Execution Context',
      'Closures, Scope Chains & Lexical Environment',
      'Prototypes, Classes, & Memory Management',
    ],
    intermediate: [
      'Array Methods (map, filter, reduce)',
      'DOM Manipulation & Event Bubbling',
      'Fetch API & JSON Handling',
      'ES6+ Syntax & Destructuring',
    ],
    basic: [
      'Variables (let/const) & Data Types',
      'Conditional Logic & Functions',
      'Loops & Basic Arrays',
      'Basic String & Number Methods',
    ],
    default: [
      'Asynchronous JavaScript & Event Loop',
      'Core Language Mechanics & Scope',
      'Modern ES6+ Syntax & Patterns',
    ],
  },
  react: {
    advanced: [
      'Component Lifecycle & Custom Hooks Design',
      'Memoization & Rendering Performance (useMemo, useCallback)',
      'State Architecture & Context Optimization',
      'Concurrent Features & Code Splitting',
    ],
    intermediate: [
      'State & Props Management (useState, useEffect)',
      'Controlled Forms & Form Validation',
      'Component Composition & Reusability',
      'Routing & API Integration',
    ],
    basic: [
      'JSX Syntax & Element Rendering',
      'Functional Components',
      'Basic Props & Event Handling',
      'Simple State Updates',
    ],
    default: [
      'React Hooks & Performance Optimization',
      'State Architecture & Component Patterns',
    ],
  },
  typescript: {
    advanced: [
      'Conditional & Mapped Types',
      'Generics & Utility Types (Pick, Omit, Record)',
      'Strict Null Checking & Type Narrowing',
      'Type-Safe API Contracts & Decorators',
    ],
    intermediate: [
      'Interfaces vs Type Aliases',
      'Union & Intersection Types',
      'Typing React Components & Hooks',
      'Enums & Type Assertions',
    ],
    basic: [
      'Primitive Types & Type Annotations',
      'Basic Object & Array Typing',
      'Function Parameter & Return Types',
    ],
    default: [
      'Generics & Advanced Type System',
      'Type Narrowing & Interface Contracts',
    ],
  },
  python: {
    advanced: [
      'Metaclasses, Decorators, & Dunder Methods',
      'Asyncio & Concurrency (Threads vs Processes)',
      'Memory Profiling & Generator Pipelines',
      'Packaging & Type Hinting (typing module)',
    ],
    intermediate: [
      'List/Dict Comprehensions & Generators',
      'OOP: Inheritance & Polymorphism',
      'Error Handling & Context Managers (with)',
      'Virtual Environments & Dependencies',
    ],
    basic: [
      'Variables, Lists, Tuples & Dictionaries',
      'Functions & Parameter Passing',
      'Basic File I/O & String Operations',
    ],
    default: [
      'Pythonic Idioms & Data Structures',
      'OOP, Generators, & Error Handling',
    ],
  },
  postgresql: {
    advanced: [
      'Query Plan Analysis (EXPLAIN ANALYZE)',
      'Indexing Strategies (B-Tree, GIN, Partial Indexes)',
      'Transactions & ACID Isolation Levels',
      'Partitioning, Replication, & Connection Pooling',
    ],
    intermediate: [
      'Complex Joins (INNER, LEFT, FULL)',
      'Aggregation & Window Functions',
      'Foreign Keys, Constraints, & Cascades',
      'Schema Migrations & Indexing Basics',
    ],
    basic: [
      'Basic CRUD Queries (SELECT, INSERT, UPDATE, DELETE)',
      'WHERE Filters & ORDER BY',
      'Basic Primary Keys & Tables',
    ],
    default: [
      'Indexing & Query Performance Tuning',
      'Window Functions & Transaction Isolation',
    ],
  },
  docker: {
    default: [
      'Multi-Stage Dockerfiles for Production',
      'Container Networking & Bridge Networks',
      'Volume Persistence & Bind Mounts',
      'Docker Compose Service Orchestration',
    ],
  },
  aws: {
    default: [
      'IAM Security Policies & Least Privilege Roles',
      'S3 Bucket Configuration & CloudFront Distribution',
      'EC2 / ECS Container Deployment',
      'VPC Fundamentals & Security Groups',
    ],
  },
};

/**
 * Generates tailored interview forecast questions based on identified candidate gaps and requirements.
 */
export function getInterviewQuestions(skillsList = [], gapsList = []) {
  const questions = [];

  // Question 1: Focused on confirmed gap or lowest scoring skill
  const primaryGap =
    gapsList[0] ||
    skillsList.find((s) => s.total_score !== null && s.total_score < 0.5) ||
    skillsList[0];

  if (primaryGap) {
    const sName = (primaryGap.skill || '').toLowerCase();
    if (sName.includes('javascript')) {
      questions.push({
        topic: 'JavaScript Mechanics (High Probability)',
        question:
          'Can you explain the execution order between microtasks (Promises, queueMicrotask) and macrotasks (setTimeout, I/O) in the JavaScript event loop?',
        hint: 'Interviewers look for understanding of why Promise.then() runs before setTimeout(..., 0).',
      });
    } else if (sName.includes('react')) {
      questions.push({
        topic: 'React Architecture (High Probability)',
        question:
          'How do you diagnose and prevent unnecessary re-renders in a deeply nested React component tree when using global state?',
        hint: 'Discuss useMemo, useCallback, React.memo, and state co-location.',
      });
    } else if (sName.includes('python')) {
      questions.push({
        topic: 'Python Concurrency (High Probability)',
        question:
          'How does the Global Interpreter Lock (GIL) impact CPU-bound multi-threading in Python, and how would you bypass it for concurrent tasks?',
        hint: 'Mention multiprocessing, asyncio for I/O bound tasks, and native C extensions.',
      });
    } else {
      questions.push({
        topic: `${primaryGap.skill} Core Standard (High Probability)`,
        question: `How do you structure production-grade architecture and error-handling in ${primaryGap.skill} at an enterprise level?`,
        hint: 'Emphasize reliability, logging, clean interfaces, and edge-case handling.',
      });
    }
  }

  // Question 2: Focused on second key required skill or architecture
  const secondSkill =
    skillsList.find(
      (s) =>
        s.skill.toLowerCase() !== primaryGap?.skill.toLowerCase() &&
        (s.importance || 'required').toLowerCase() !== 'preferred'
    ) || skillsList[1];

  if (secondSkill) {
    const sName = (secondSkill.skill || '').toLowerCase();
    if (sName.includes('typescript')) {
      questions.push({
        topic: 'TypeScript Type Safety',
        question:
          'How do you type unknown external API responses safely using generics and type guards rather than resorting to any?',
        hint: 'Discuss the unknown type, Zod / custom type guards, and discriminated unions.',
      });
    } else if (sName.includes('postgres') || sName.includes('sql')) {
      questions.push({
        topic: 'Database Performance',
        question:
          'When a critical query slows down under high traffic, what steps do you take with EXPLAIN ANALYZE to identify index bottlenecks?',
        hint: 'Look for Seq Scans vs Index Scans, cost estimates, and high row filter percentages.',
      });
    } else {
      questions.push({
        topic: `${secondSkill.skill} Best Practices`,
        question: `What patterns do you implement in ${secondSkill.skill} to ensure high testability, maintainability, and code quality?`,
        hint: 'Focus on separation of concerns, automated unit testing, and dependency injection.',
      });
    }
  }

  // Question 3: System Design / Practical Integration question
  questions.push({
    topic: 'Full-Stack Integration & Reliability',
    question:
      'How do you handle graceful degradation and retry strategies when backend API services or database queries experience transient latency spikes?',
    hint: 'Mention exponential backoff with jitter, circuit breakers, optimistic UI updates, and caching.',
  });

  return questions;
}
