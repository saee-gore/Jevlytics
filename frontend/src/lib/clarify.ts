// Options shown when the assistant answers "clarification_required". The backend returns only a
// status and a sentence for these, with no suggestions, so the options are chosen here from the
// topic of the original question. Each option is a complete, specific question that the user can
// send with one click. This is a frontend convenience, not a backend contract.
export interface ClarifyOption {
  label: string;
  question: string;
}

const TOPICS: { match: RegExp; options: ClarifyOption[] }[] = [
  {
    match: /declin/i,
    options: [
      { label: "Decline rate by card network", question: "What is our decline rate by card network last month?" },
      { label: "Most common decline reasons", question: "What are our most common decline reasons last month?" },
      { label: "Credit vs debit decline rates", question: "Compare credit and debit card performance last month." },
    ],
  },
  {
    match: /chargeback/i,
    options: [
      { label: "Chargeback rate this quarter", question: "What was our chargeback rate this quarter?" },
      { label: "Chargeback rate by region", question: "Did our chargeback rate change by region this quarter?" },
      { label: "Chargeback rate by card type", question: "What was our chargeback rate by card type this quarter?" },
    ],
  },
  {
    match: /settl/i,
    options: [
      { label: "Settled volume last month", question: "How much transaction volume was settled last month?" },
      { label: "Settled volume this quarter", question: "How much transaction volume was settled this quarter?" },
    ],
  },
  {
    match: /region|location|country/i,
    options: [
      { label: "Volume by region", question: "Show transaction volume by region this quarter." },
      { label: "Volume by region and card type", question: "Show transaction volume by region for credit cards this quarter." },
    ],
  },
  {
    match: /volume|transaction|count|how many/i,
    options: [
      { label: "Transaction volume this quarter", question: "What was our transaction volume this quarter?" },
      { label: "Transaction count last month", question: "How many transactions did we process last month?" },
      { label: "Volume by currency", question: "What was our approved volume per currency last month?" },
      { label: "Credit vs debit volume", question: "Compare credit and debit card performance last month." },
    ],
  },
];

const GENERAL: ClarifyOption[] = [
  { label: "Transaction volume", question: "What was our transaction volume last month?" },
  { label: "Decline rate", question: "What is our decline rate by card network last month?" },
  { label: "Settlements", question: "How much transaction volume was settled last month?" },
  { label: "Chargebacks", question: "What was our chargeback rate this quarter?" },
];

/** Up to four specific questions to offer after a clarification request. */
export function clarifyOptions(question: string): ClarifyOption[] {
  const topic = TOPICS.find((t) => t.match.test(question));
  return (topic?.options ?? GENERAL).slice(0, 4);
}
