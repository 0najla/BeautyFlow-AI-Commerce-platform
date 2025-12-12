

-- Clear existing data (for testing)
TRUNCATE TABLE group_messages CASCADE;
TRUNCATE TABLE group_products CASCADE;
TRUNCATE TABLE group_members CASCADE;
TRUNCATE TABLE shipping_groups CASCADE;
TRUNCATE TABLE sfda_certificates CASCADE;

-- ========================================
-- SAMPLE SHIPPING GROUPS
-- ========================================

-- Group 1: Riyadh → Shanghai (Almost Full, Urgent)
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g001',
    'riyadh',
    'china',
    5,
    4,
    200.00,
    160.00,
    950.00,
    CURRENT_TIMESTAMP + INTERVAL '18 hours',
    'active',
    TRUE,
    'user1'
);

-- Group 2: Jeddah → Istanbul (Medium)
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g002',
    'jeddah',
    'turkey',
    4,
    2,
    150.00,
    80.00,
    1200.00,
    CURRENT_TIMESTAMP + INTERVAL '3 days',
    'active',
    TRUE,
    'user5'
);

-- Group 3: Dammam → Seoul (New Group)
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g003',
    'dammam',
    'korea',
    5,
    1,
    200.00,
    50.00,
    1050.00,
    CURRENT_TIMESTAMP + INTERVAL '5 days',
    'active',
    TRUE,
    'user8'
);

-- Group 4: Jeddah → Guangzhou (Your Current Group - for demo)
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g004',
    'jeddah',
    'china',
    5,
    3,
    200.00,
    75.00,
    1120.00,
    CURRENT_TIMESTAMP + INTERVAL '2 days',
    'active',
    TRUE,
    'current_user'
);

-- Group 5: Mecca → Dubai (UAE - Fast)
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g005',
    'mecca',
    'uae',
    4,
    3,
    120.00,
    90.00,
    650.00,
    CURRENT_TIMESTAMP + INTERVAL '1 day',
    'active',
    TRUE,
    'user12'
);

-- Group 6: Tabuk → London (Premium)
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g006',
    'tabuk',
    'uk',
    5,
    2,
    180.00,
    70.00,
    1850.00,
    CURRENT_TIMESTAMP + INTERVAL '7 days',
    'active',
    TRUE,
    'user15'
);

-- Group 7: Completed Example
INSERT INTO shipping_groups (
    id, origin_location, destination, max_capacity, current_members,
    max_weight, current_weight, cost_per_person, ship_date,
    status, sfda_verified, created_by
) VALUES (
    'g007',
    'riyadh',
    'china',
    5,
    5,
    200.00,
    200.00,
    920.00,
    CURRENT_TIMESTAMP - INTERVAL '3 days',
    'completed',
    TRUE,
    'user20'
);

-- ========================================
-- SAMPLE GROUP MEMBERS
-- ========================================

-- Group g001 members (Riyadh → Shanghai)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g001', 'user10', 40.00, 950.00, 'active'),
('g001', 'user11', 45.00, 950.00, 'active'),
('g001', 'user12', 35.00, 950.00, 'active'),
('g001', 'user13', 40.00, 950.00, 'active');

-- Group g002 members (Jeddah → Istanbul)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g002', 'user5', 50.00, 1200.00, 'active'),
('g002', 'user21', 30.00, 1200.00, 'active');

-- Group g003 members (Dammam → Seoul)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g003', 'user8', 50.00, 1050.00, 'active');

-- Group g004 members (YOUR GROUP - Jeddah → Guangzhou)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g004', 'current_user', 15.00, 1120.00, 'active'),
('g004', 'user_sarah', 30.00, 1120.00, 'active'),
('g004', 'user_fatima', 30.00, 1120.00, 'active');

-- Group g005 members (Mecca → Dubai)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g005', 'user12', 30.00, 650.00, 'active'),
('g005', 'user30', 35.00, 650.00, 'active'),
('g005', 'user31', 25.00, 650.00, 'active');

-- Group g006 members (Tabuk → London)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g006', 'user15', 40.00, 1850.00, 'active'),
('g006', 'user40', 30.00, 1850.00, 'active');

-- Group g007 members (Completed)
INSERT INTO group_members (group_id, user_id, weight_contribution, cost_share, status) VALUES
('g007', 'user20', 40.00, 920.00, 'active'),
('g007', 'user50', 40.00, 920.00, 'active'),
('g007', 'user51', 40.00, 920.00, 'active'),
('g007', 'user52', 40.00, 920.00, 'active'),
('g007', 'user53', 40.00, 920.00, 'active');

-- ========================================
-- SAMPLE GROUP PRODUCTS
-- ========================================

-- Products in YOUR GROUP (g004)
INSERT INTO group_products (group_id, user_id, product_id, quantity, weight, sfda_verified) VALUES
('g004', 'current_user', 'prod_lip_001', 5, 15.00, TRUE),
('g004', 'user_sarah', 'prod_mas_002', 10, 30.00, TRUE),
('g004', 'user_fatima', 'prod_fnd_003', 8, 30.00, TRUE);

-- Products in g001
INSERT INTO group_products (group_id, user_id, product_id, quantity, weight, sfda_verified) VALUES
('g001', 'user10', 'prod_skn_004', 12, 40.00, TRUE),
('g001', 'user11', 'prod_lip_005', 15, 45.00, TRUE),
('g001', 'user12', 'prod_mas_006', 10, 35.00, TRUE),
('g001', 'user13', 'prod_blh_007', 8, 40.00, TRUE);

-- Products in g002
INSERT INTO group_products (group_id, user_id, product_id, quantity, weight, sfda_verified) VALUES
('g002', 'user5', 'prod_frag_008', 20, 50.00, TRUE),
('g002', 'user21', 'prod_hair_009', 10, 30.00, TRUE);

-- ========================================
-- SAMPLE GROUP MESSAGES (Chat)
-- ========================================

-- Messages in YOUR GROUP (g004)
INSERT INTO group_messages (group_id, user_id, message, created_at, read_by) VALUES
('g004', 'user_sarah', 'Hey everyone! Excited to share this shipment 🎉', 
 CURRENT_TIMESTAMP - INTERVAL '2 hours', 
 '["current_user", "user_fatima"]'::jsonb),

('g004', 'user_fatima', 'Same here! This is my third merge, saves so much money!', 
 CURRENT_TIMESTAMP - INTERVAL '1 hour', 
 '["current_user", "user_sarah"]'::jsonb),

('g004', 'current_user', 'Great! When do we expect shipment?', 
 CURRENT_TIMESTAMP - INTERVAL '30 minutes', 
 '["user_sarah", "user_fatima"]'::jsonb),

('g004', 'user_sarah', 'It should ship in 2 days once we get 2 more members!', 
 CURRENT_TIMESTAMP - INTERVAL '15 minutes', 
 '["current_user"]'::jsonb);

-- Messages in g001
INSERT INTO group_messages (group_id, user_id, message, created_at) VALUES
('g001', 'user10', 'Ready to ship tomorrow?', CURRENT_TIMESTAMP - INTERVAL '3 hours'),
('g001', 'user11', 'Yes! All my products are packed.', CURRENT_TIMESTAMP - INTERVAL '2 hours'),
('g001', 'user12', 'Same here. Tracking number will be shared soon!', CURRENT_TIMESTAMP - INTERVAL '1 hour');

-- ========================================
-- SAMPLE SFDA CERTIFICATES
-- ========================================

INSERT INTO sfda_certificates (product_id, certificate_number, issue_date, expiry_date, status) VALUES
('prod_lip_001', 'SFDA-COS-2024-001', '2024-01-15', '2026-01-15', 'valid'),
('prod_mas_002', 'SFDA-COS-2024-002', '2024-02-20', '2026-02-20', 'valid'),
('prod_fnd_003', 'SFDA-COS-2024-003', '2024-03-10', '2026-03-10', 'valid'),
('prod_skn_004', 'SFDA-SKN-2024-004', '2024-01-25', '2026-01-25', 'valid'),
('prod_lip_005', 'SFDA-COS-2024-005', '2024-04-05', '2026-04-05', 'valid'),
('prod_mas_006', 'SFDA-COS-2024-006', '2024-03-15', '2026-03-15', 'valid'),
('prod_blh_007', 'SFDA-COS-2024-007', '2024-02-28', '2026-02-28', 'valid'),
('prod_frag_008', 'SFDA-FRG-2024-008', '2024-01-10', '2026-01-10', 'valid'),
('prod_hair_009', 'SFDA-HAR-2024-009', '2024-03-20', '2026-03-20', 'valid');

-- ========================================
-- SAMPLE STATISTICS (for dashboard)
-- ========================================

-- Create a simple stats view
CREATE OR REPLACE VIEW cost_sharing_stats AS
SELECT
    (SELECT COUNT(*) FROM shipping_groups WHERE status = 'active') as active_groups,
    (SELECT COUNT(DISTINCT user_id) FROM group_members WHERE status = 'active') as total_users,
    (SELECT COUNT(*) FROM shipping_groups WHERE status = 'completed') as completed_shipments,
    (SELECT COALESCE(SUM(cost_per_person * (max_capacity - current_members)), 0) 
     FROM shipping_groups 
     WHERE status = 'active') as potential_savings;

-- ========================================
-- USEFUL QUERIES FOR TESTING
-- ========================================

-- Query 1: Get all active groups with member count
/*
SELECT 
    sg.id,
    sg.origin_location,
    sg.destination,
    sg.current_members || '/' || sg.max_capacity as capacity,
    sg.current_weight || '/' || sg.max_weight as weight,
    sg.cost_per_person,
    sg.ship_date,
    sg.sfda_verified
FROM shipping_groups sg
WHERE sg.status = 'active'
ORDER BY sg.ship_date ASC;
*/

-- Query 2: Get user's current group with all details
/*
SELECT 
    sg.*,
    json_agg(
        json_build_object(
            'user_id', gm.user_id,
            'weight', gm.weight_contribution,
            'cost', gm.cost_share
        )
    ) as members
FROM shipping_groups sg
INNER JOIN group_members gm ON sg.id = gm.group_id
WHERE gm.user_id = 'current_user'
  AND gm.status = 'active'
  AND sg.status = 'active'
GROUP BY sg.id;
*/

-- Query 3: Get recent messages for a group
/*
SELECT 
    gm.id,
    gm.user_id,
    gm.message,
    gm.created_at,
    gm.read_by
FROM group_messages gm
WHERE gm.group_id = 'g004'
ORDER BY gm.created_at DESC
LIMIT 20;
*/

-- Query 4: Calculate total savings per user
/*
SELECT 
    gm.user_id,
    COUNT(DISTINCT gm.group_id) as groups_joined,
    SUM(gm.cost_share) as total_spent,
    -- Assuming solo cost is 2.5x shared cost (60% savings)
    SUM(gm.cost_share * 2.5) - SUM(gm.cost_share) as total_saved
FROM group_members gm
INNER JOIN shipping_groups sg ON gm.group_id = sg.id
WHERE sg.status = 'completed'
GROUP BY gm.user_id
ORDER BY total_saved DESC;
*/

-- Query 5: Find matching groups for a user
/*
SELECT 
    sg.id,
    sg.origin_location,
    sg.destination,
    sg.cost_per_person,
    (sg.max_weight - sg.current_weight) as available_weight,
    (sg.max_capacity - sg.current_members) as available_spots,
    EXTRACT(EPOCH FROM (sg.ship_date - CURRENT_TIMESTAMP))/86400 as days_until_ship
FROM shipping_groups sg
WHERE sg.status = 'active'
  AND sg.origin_location = 'jeddah'  -- User's location
  AND sg.destination = 'china'        -- User's destination
  AND (sg.max_capacity - sg.current_members) > 0
  AND (sg.max_weight - sg.current_weight) >= 50  -- User's weight
ORDER BY sg.ship_date ASC;
*/

-- ========================================
-- VERIFICATION QUERIES
-- ========================================

-- Check data was inserted correctly
SELECT 'Shipping Groups' as table_name, COUNT(*) as count FROM shipping_groups
UNION ALL
SELECT 'Group Members', COUNT(*) FROM group_members
UNION ALL
SELECT 'Group Products', COUNT(*) FROM group_products
UNION ALL
SELECT 'Group Messages', COUNT(*) FROM group_messages
UNION ALL
SELECT 'SFDA Certificates', COUNT(*) FROM sfda_certificates;

-- Should show:
-- Shipping Groups: 7
-- Group Members: 18
-- Group Products: 9
-- Group Messages: 7
-- SFDA Certificates: 9

-- ========================================
-- CLEANUP (if needed)
-- ========================================

/*
-- To start fresh, run:
TRUNCATE TABLE group_messages CASCADE;
TRUNCATE TABLE group_products CASCADE;
TRUNCATE TABLE group_members CASCADE;
TRUNCATE TABLE shipping_groups CASCADE;
TRUNCATE TABLE sfda_certificates CASCADE;

-- Then re-run this entire file
*/

-- ========================================
-- SUCCESS MESSAGE
-- ========================================

DO $$
BEGIN
    RAISE NOTICE '✅ Sample data loaded successfully!';
    RAISE NOTICE '📊 7 groups, 18 members, 9 products, 7 messages, 9 certificates';
    RAISE NOTICE '🚀 You can now test the Cost Sharing system!';
END $$;