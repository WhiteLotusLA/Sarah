-- Finance-related database tables for Sarah AI

-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('checking', 'savings', 'credit', 'investment', 'loan')),
    balance DECIMAL(15, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    institution VARCHAR(255),
    account_number_encrypted TEXT, -- Encrypted account number
    routing_number_encrypted TEXT, -- Encrypted routing number
    credit_limit DECIMAL(15, 2), -- For credit accounts
    interest_rate DECIMAL(5, 4), -- For loans/savings
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    amount DECIMAL(15, 2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL CHECK (transaction_type IN ('income', 'expense', 'transfer')),
    category VARCHAR(100),
    subcategory VARCHAR(100),
    description TEXT,
    merchant VARCHAR(255),
    transaction_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    posted_date TIMESTAMPTZ,
    is_pending BOOLEAN DEFAULT false,
    is_recurring BOOLEAN DEFAULT false,
    recurring_transaction_id UUID REFERENCES recurring_transactions(id),
    transfer_to_account_id UUID REFERENCES accounts(id), -- For transfers
    tags TEXT[], -- Array of tags
    receipt_url TEXT, -- Link to receipt image/document
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Budgets table
CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    period VARCHAR(50) NOT NULL CHECK (period IN ('daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'annually')),
    start_date DATE NOT NULL,
    end_date DATE,
    rollover_unused BOOLEAN DEFAULT false,
    alert_threshold DECIMAL(5, 2) DEFAULT 80.00, -- Alert when X% of budget is used
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Bills table
CREATE TABLE IF NOT EXISTS bills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id), -- Account to pay from
    payee VARCHAR(255) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    due_day INTEGER CHECK (due_day >= 1 AND due_day <= 31), -- Day of month
    due_date DATE, -- For one-time bills
    category VARCHAR(100),
    is_recurring BOOLEAN DEFAULT true,
    recurrence_type VARCHAR(50) CHECK (recurrence_type IN ('daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'annually')),
    auto_pay BOOLEAN DEFAULT false,
    reminder_days INTEGER DEFAULT 3, -- Days before due date to remind
    last_paid_date DATE,
    next_due_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Recurring transactions template
CREATE TABLE IF NOT EXISTS recurring_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    amount DECIMAL(15, 2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL CHECK (transaction_type IN ('income', 'expense')),
    category VARCHAR(100),
    description TEXT,
    merchant VARCHAR(255),
    recurrence_type VARCHAR(50) NOT NULL CHECK (recurrence_type IN ('daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'annually')),
    start_date DATE NOT NULL,
    end_date DATE,
    last_processed_date DATE,
    next_scheduled_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Financial goals table
CREATE TABLE IF NOT EXISTS financial_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    goal_type VARCHAR(50) CHECK (goal_type IN ('savings', 'debt_payoff', 'investment', 'purchase', 'emergency_fund')),
    target_amount DECIMAL(15, 2) NOT NULL,
    current_amount DECIMAL(15, 2) DEFAULT 0.00,
    target_date DATE,
    monthly_contribution DECIMAL(15, 2),
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    is_achieved BOOLEAN DEFAULT false,
    achieved_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Investment holdings table
CREATE TABLE IF NOT EXISTS investment_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id),
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    shares DECIMAL(15, 6) NOT NULL,
    cost_basis DECIMAL(15, 2),
    current_price DECIMAL(15, 4),
    current_value DECIMAL(15, 2),
    gain_loss DECIMAL(15, 2),
    gain_loss_percentage DECIMAL(8, 4),
    asset_type VARCHAR(50) CHECK (asset_type IN ('stock', 'etf', 'mutual_fund', 'bond', 'crypto', 'commodity')),
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Financial insights/analytics table
CREATE TABLE IF NOT EXISTS financial_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    insight_type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    data JSONB, -- Flexible storage for various insight data
    severity VARCHAR(50) CHECK (severity IN ('info', 'warning', 'critical', 'positive')),
    is_actionable BOOLEAN DEFAULT false,
    action_taken BOOLEAN DEFAULT false,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date DESC);
CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_budgets_user_active ON budgets(user_id, is_active);
CREATE INDEX idx_bills_user_due ON bills(user_id, next_due_date);
CREATE INDEX idx_bills_auto_pay ON bills(auto_pay, is_active);
CREATE INDEX idx_financial_goals_user ON financial_goals(user_id, is_active);
CREATE INDEX idx_financial_insights_user ON financial_insights(user_id, created_at DESC);

-- Create triggers for updated_at
CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_budgets_updated_at BEFORE UPDATE ON budgets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_bills_updated_at BEFORE UPDATE ON bills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_recurring_transactions_updated_at BEFORE UPDATE ON recurring_transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_financial_goals_updated_at BEFORE UPDATE ON financial_goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Create views for common queries
CREATE OR REPLACE VIEW monthly_spending_by_category AS
SELECT 
    user_id,
    category,
    DATE_TRUNC('month', transaction_date) as month,
    SUM(amount) as total_spent,
    COUNT(*) as transaction_count,
    AVG(amount) as average_transaction
FROM transactions
WHERE transaction_type = 'expense'
GROUP BY user_id, category, DATE_TRUNC('month', transaction_date);

CREATE OR REPLACE VIEW net_worth_summary AS
SELECT 
    user_id,
    SUM(CASE WHEN account_type IN ('checking', 'savings', 'investment') THEN balance ELSE 0 END) as total_assets,
    SUM(CASE WHEN account_type IN ('credit', 'loan') THEN balance ELSE 0 END) as total_liabilities,
    SUM(CASE WHEN account_type IN ('checking', 'savings', 'investment') THEN balance 
             WHEN account_type IN ('credit', 'loan') THEN -balance 
             ELSE 0 END) as net_worth
FROM accounts
WHERE is_active = true
GROUP BY user_id;

-- Add comments for documentation
COMMENT ON TABLE accounts IS 'User financial accounts including checking, savings, credit cards, and investments';
COMMENT ON TABLE transactions IS 'All financial transactions across user accounts';
COMMENT ON TABLE budgets IS 'User-defined budgets by category and time period';
COMMENT ON TABLE bills IS 'Recurring bills and payment reminders';
COMMENT ON TABLE financial_goals IS 'User financial goals and progress tracking';
COMMENT ON TABLE investment_holdings IS 'Investment portfolio holdings and performance';
COMMENT ON TABLE financial_insights IS 'AI-generated financial insights and recommendations';