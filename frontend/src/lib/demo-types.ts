// Shape of one demo transaction. Demo data only: the live API has no endpoint that lists transactions.
export interface DemoTransaction {
  id: string;
  at: string;
  cardType: string;
  network: string;
  amount: number;
  currency: string;
  status: string;
  declineReason: string | null;
  region: string;
}
