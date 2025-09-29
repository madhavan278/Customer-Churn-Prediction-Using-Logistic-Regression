// Common utility functions
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// For Prediction Explorer
document.addEventListener('DOMContentLoaded', function() {
    // Initialize any page-specific scripts
    if (document.getElementById('probability_value')) {
        // This is the prediction explorer page
        initializeExplorer();
    }
});

function initializeExplorer() {
    // Set up event listeners for all inputs
    document.querySelectorAll('input[type="range"], input[type="number"], select').forEach(input => {
        input.addEventListener('input', updateLivePrediction);
    });
    
    // Set up save button if it exists
    const saveBtn = document.getElementById('save_btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', savePrediction);
    }
}

async function updateLivePrediction() {
    const features = {};
    
    // Get all feature values from the explorer page
    const featureElements = {
        'credit_score': document.getElementById('credit_score'),
        'age': document.getElementById('age'),
        'balance': document.getElementById('balance'),
        'estimated_salary': document.getElementById('estimated_salary'),
        'tenure': document.getElementById('tenure'),
        'products_number': document.getElementById('products_number'),
        'credit_card': document.getElementById('credit_card'),
        'active_member': document.getElementById('active_member')
    };
    
    for (const [key, element] of Object.entries(featureElements)) {
        if (element) {
            features[key] = element.type === 'select-one' ? 
                parseInt(element.value) : 
                parseFloat(element.value);
        }
    }
    
    try {
        const response = await fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(features)
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Update the probability meter
        const probability = data.probability * 100;
        document.getElementById('probability_value').textContent = probability.toFixed(1) + '%';
        document.getElementById('probability_bar').style.width = probability + '%';
        
        // Update prediction text
        const predictionText = probability >= 50 ? 
            `HIGH RISK (${probability.toFixed(1)}% chance of churn)` : 
            `LOW RISK (${probability.toFixed(1)}% chance of churn)`;
        
        const predictionElement = document.getElementById('prediction_text');
        predictionElement.textContent = predictionText;
        predictionElement.className = 'prediction-text ' + (probability >= 50 ? 'high-risk' : 'low-risk');
        
        // Show most important feature
        const importantFeature = Object.entries(data.feature_importance).reduce(
            (a, b) => a[1] > b[1] ? a : b
        )[0];
        document.getElementById('important_factor').textContent = 
            `Most influential factor: ${importantFeature.replace('_', ' ')}`;
            
    } catch (error) {
        console.error('Prediction error:', error);
        document.getElementById('prediction_text').textContent = 'Error: ' + error.message;
        document.getElementById('prediction_text').className = 'prediction-text error';
    }
}

async function savePrediction() {
    const features = {};
    
    // Get all feature values
    const featureElements = {
        'credit_score': document.getElementById('credit_score'),
        'age': document.getElementById('age'),
        'balance': document.getElementById('balance'),
        'estimated_salary': document.getElementById('estimated_salary'),
        'tenure': document.getElementById('tenure'),
        'products_number': document.getElementById('products_number'),
        'credit_card': document.getElementById('credit_card'),
        'active_member': document.getElementById('active_member')
    };
    
    for (const [key, element] of Object.entries(featureElements)) {
        if (element) {
            features[key] = element.type === 'select-one' ? 
                parseInt(element.value) : 
                parseFloat(element.value);
        }
    }
    
    try {
        // First get the prediction
        const response = await fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(features)
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Then save to history
        const formData = new FormData();
        for (const [key, value] of Object.entries(features)) {
            formData.append(key, value);
        }
        formData.append('prediction', data.churn ? 'Yes' : 'No');
        formData.append('probability', data.probability);
        
        const saveResponse = await fetch('/save_prediction', {
            method: 'POST',
            body: formData
        });
        
        const saveData = await saveResponse.json();
        
        if (saveData.error) {
            throw new Error(saveData.error);
        }
        
        alert('Prediction saved to your history!');
        window.location.href = '/history';
    } catch (error) {
        console.error('Save error:', error);
        alert('Failed to save prediction: ' + error.message);
    }
}