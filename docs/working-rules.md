# Working rules

Generic rules for writing and organising code, to be copied as they are into another project.
Nothing here is specific to one application: what belongs to a project (modules, examples, decisions)
is in its own documents, and the numeric limits checked by the tools (size of a function, number of
arguments, complexity) live in the configuration of those tools, not here.

## Structure and size

- One responsibility per file. If its purpose cannot be said in one sentence without "and", it does
  too much. Split by reason to change, not by size: what changes together stays together.
- A source file rarely goes over 400 lines and never over 600. When a file gets close, split it
  before adding to it. A class rarely goes over 300 lines (see "Splitting a class").
- A new feature gets its own module. A big file, such as a main window, only receives the wiring.
- Do not split too fine: ten files of forty lines that call each other cost more to read than one.
  Do not split by technical kind (a file of "constants", a file of "utilities"): split by subject.
  A name that says what the file holds is a sign of a good split.
- Layers: the user interface layer only does layout and wiring. Any logic that can be tested
  without a window goes to the logic layer, which never imports the interface layer. No circular
  dependencies: they go one way.
- Worker threads never touch the interface; they hand their results over to the interface thread.
- Shared state is explicit: components receive a context object or callbacks, they do not reach
  into each other's attributes.

## Splitting a class

1. **Find the groups first.** Group the methods by the attributes they use. A group that uses only
   part of the state of the class can be extracted. Section comments inside a class mark the groups.
2. **Extract by composition.** The class owns the new object and calls it. No mixin, no base class
   made only to share code: they split the file but not the state, which stays tied together.
3. **Hand over only what is needed.** The new class receives, in its constructor, a state object or
   callbacks. It never receives the whole original object.
4. **One reason to change per class** (for example menus, the events of a run, the conversations).
5. **Logic that touches no control of the interface** goes to the logic layer and is tested without
   a window.
6. **One extraction at a time.** The complete suite passes before and after, with one commit per
   extraction. A move never comes with a change of behaviour.
7. **Warning signs.** The new class calls the old one back in every direction; a "manager" class that
   collects what was left over; a split made by line count instead of by subject.

## When a tool says the code is too big or too complex

A tool detects the problem, not the cause. Decide in this order:

1. **Does the function do two things?** Then split it into named functions. It is the most frequent
   cause, and it fixes too many arguments, branches and statements at once.
2. **Do the values travel together?** If several functions receive the same values, group them in a
   small typed object (a dataclass) with a meaning of its own. Reuse one that already exists.
3. **Is it a long chain of conditions?** Replace it with a table or extract named conditions.
4. **Is it only description** (labels and names of a dialog)? Group it in a description object,
   or, for the interface layer only, raise the limit in the configuration of the tool.

**Grouping arguments.** Too many arguments: group the *data* in a small dataclass named after
what it describes (`ListSpec`, not `Params`), holding only values that go together. Keep behaviour
and platform types (callbacks, the parent window, interface-library identifiers) as separate
arguments, so the object never imports the interface library.

Never work around an alert with an untyped dictionary or `**kwargs`. Never silence one without a
sentence that says why, and tell the user when it is done.

## At each milestone

- A file or a class over its size limit is a warning, not a failure. When proposing a commit,
  report the warnings of the size check to the user (which file or class, its size) and let the
  user decide whether to split. Do not split, move code or change a limit without being asked.
- Before proposing a commit, check the size of the files that were touched and split those that
  are over the limit.
- While working, run the tests that concern the change; run the complete suite and the checks
  (lint, format, types) once, just before proposing the commit.

## Tests

- One test file per module. A test that needs a real window to check logic shows that the logic
  is in the wrong place.
- Tests never read the real configuration of the user: it is redirected to a temporary folder.
  A fake replaces every external program, whatever it costs to run.
- A manual test with the real external program uses its cheapest model and settings.
- Do not guess a protocol or an output format: look at a real run, and write down what was
  verified in the documentation of that program.

## Reading and context

- Read a big file by ranges rather than whole. Every call sends the whole context again, so what
  is read early is paid again at each step.
- Keep the file that is always loaded short: the rule in a line or two, the reasons and the
  examples in a document that is read on demand.

## Files and data

- A file of the application is written to a temporary file in the same folder, then moved over the
  old one: a crash never leaves a half-written file.
- The last valid version is kept as a backup. A file that cannot be read is set aside, not
  overwritten, so nothing is lost. At reading, a damaged file gives its backup, else the default
  values, and the user is told with a dialog, not with a crash.
- A file that belongs to another program (its settings, for example) is read with care: if it is
  not valid it is never overwritten, and the other keys of a valid one are kept when it is written.
- Only one instance of the application writes the files of a user.

## Texts and languages

- Every visible text goes through the translation function; no concatenation of texts, a text
  with named fields instead. The catalog is compiled again after each edit.
- Access keys are unique inside a dialog, in every language.

## Accessible interfaces

- Everything is usable from the keyboard alone. Every control has an accessible name and every
  dialog a defined initial focus.
- A label is created right before its control, so that screen readers pair them.
- The accessible name of a control is its label without the access key marker: the text is
  written once and the name is derived from it. A control whose name must differ from its
  label is the exception, and its name is written out.
- No unexpected change of focus. Where the focus and the caret go in each case is written down
  and every new feature follows a rule or adds its case.
- Native controls first. A read-only field is a multi-line text field, which the Tab key reaches.
- No information given by colour alone.
- What cannot be used is greyed, not hidden and not silent.
- Information shown in a list goes in the text of each line, separated by commas, leaving out what
  has no value; nothing depends on columns.
- What the application says (a result, a change of state) is said through one announcement
  center, using what the platform offers for assistive technologies, not an API of one vendor.
- Accessibility is verified by hand with the screen readers at each milestone.
